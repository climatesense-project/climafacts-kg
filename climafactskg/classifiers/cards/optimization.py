"""GEPA-based prompt optimization for the CARDS LLM classifier."""

import asyncio
import dataclasses
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from gepa.api import optimize
from gepa.core.adapter import EvaluationBatch, GEPAAdapter
from pydantic_evals import Case, Dataset

from .evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch
from .llm.classifier import CARDSLLMClassifier, CARDSOutput, _build_pydantic_ai_model

# GEPA's default reflection prompt shows the reflection LM the failure feedback
# and asks it to "write a new instruction for the assistant" from it. Nothing
# stops the reflection LM from writing meta-references to that feedback loop
# straight into the candidate instruction (e.g. "cross-reference with the
# feedback provided") — which is meaningless at inference time, since the
# deployed classifier only ever receives the instruction text plus the claim,
# never any feedback or prior responses. This template makes that constraint
# explicit.
_SELF_CONTAINED_REFLECTION_PROMPT_TEMPLATE = (
    "I provided an assistant with the following instructions to perform a task for me:\n"
    "```\n"
    "<curr_param>\n"
    "```\n\n"
    "The following are examples of different task inputs provided to the assistant along with the "
    "assistant's response for each of them, and some feedback on how the assistant's response could "
    "be better:\n"
    "```\n"
    "<side_info>\n"
    "```\n\n"
    "Your task is to write a new instruction for the assistant.\n\n"
    "Read the inputs carefully and identify the input format and infer detailed task description "
    "about the task I wish to solve with the assistant.\n\n"
    "Read all the assistant responses and the corresponding feedback. Identify all niche and domain "
    "specific factual information about the task and include it in the instruction, as a lot of it "
    "may not be available to the assistant in the future. The assistant may have utilized a "
    "generalizable strategy to solve the task, if so, include that in the instruction as well.\n\n"
    "IMPORTANT: the new instruction is the ONLY thing the assistant will see at run time — it will "
    "NOT see the examples, responses, or feedback shown to you above, and it will NOT remember this "
    'reflection step. Never refer to "the feedback provided", "previous responses", "as discussed '
    'above", or any other part of this reflection process inside the new instruction. The new '
    "instruction must be fully self-contained: any lesson learned from the feedback must be "
    "rewritten as a standalone, concrete rule or piece of domain knowledge the assistant can apply "
    "to a claim it has never seen before.\n\n"
    "Provide the new instructions within ``` blocks."
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CARDSDataInst:
    """One evaluation example: a claim, its acceptable gold labels, and optional context."""

    claim: str
    expected: list[str]
    context: str | None = None


@dataclasses.dataclass
class CARDSTrajectory:
    """Per-case trace captured when ``capture_traces=True``."""

    claim: str
    predicted: str
    expected: list[str]
    score: float
    context: str | None = None


class CARDSEvalsAdapter(GEPAAdapter[CARDSDataInst, CARDSTrajectory, str]):
    """Bridges GEPA optimization with pydantic-ai + pydantic-evals.

    Each GEPA candidate (a dict ``{"instructions": "<system_prompt>"}`` ) is
    evaluated by injecting it via ``agent.override(instructions=...)`` and
    running a temporary pydantic-evals dataset. The optimization signal is an
    equal blend of :class:`.CARDSOneOfMatch` (exact match) and
    :class:`.CARDSHierarchicalMatch` (partial-credit hF1) — hF1 alone rewards
    "close enough" candidates (e.g. ones that hedge toward broad parent codes)
    even when they get the precise category wrong, which previously let a
    candidate with degenerate exact-match accuracy still look good to GEPA.
    """

    def __init__(self, classifier: CARDSLLMClassifier, concurrency: int | None = None) -> None:
        """Create a new adapter from a configured classifier.

        Args:
            classifier: A :class:`CARDSLLMClassifier` instance (e.g. from
                ``CARDSLLMClassifier.from_preset(...)``). Its agent, user prompt,
                and model settings are used as-is.
            concurrency: Maximum concurrent ``agent.run()`` calls per batch.
                Defaults to ``classifier._default_concurrency``.
        """
        self._agent = classifier._agent
        self._user_prompt = classifier._user_prompt
        self._user_prompt_with_context = classifier._user_prompt_with_context
        self._model_settings = classifier._model_settings
        self._concurrency = concurrency or classifier._default_concurrency

    def evaluate(
        self,
        batch: list[CARDSDataInst],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch[CARDSTrajectory, str]:
        # inputs carries the batch index alongside the claim text so that task()
        # can look up the right context even when two items share claim text.
        cases = [
            Case(name=str(i), inputs=(i, item.claim), expected_output=item.expected) for i, item in enumerate(batch)
        ]
        temp_dataset = Dataset(cases=cases, evaluators=[CARDSOneOfMatch(), CARDSHierarchicalMatch()])

        async def task(inputs: tuple[int, str]) -> str:
            idx, text = inputs
            context = batch[idx].context
            user_msg = (
                self._user_prompt_with_context.format(text=text, context=context)
                if context
                else self._user_prompt.format(text=text)
            )
            result = await self._agent.run(user_msg, model_settings=self._model_settings)
            out: CARDSOutput = result.output
            return out.cards_category if out.is_climate_related and out.cards_category else "0_0"

        with self._agent.override(instructions=candidate["instructions"]):
            report = asyncio.run(temp_dataset.evaluate(task, max_concurrency=self._concurrency))

        outputs = [str(c.output) for c in report.cases]

        def _blended_score(c: Any) -> float:
            exact = c.scores["CARDSOneOfMatch"].value if "CARDSOneOfMatch" in c.scores else 0.0
            hier = c.scores["CARDSHierarchicalMatch"].value if "CARDSHierarchicalMatch" in c.scores else 0.0
            return 0.5 * exact + 0.5 * hier

        scores = [_blended_score(c) for c in report.cases]
        trajectories = None
        if capture_traces:
            trajectories = [
                CARDSTrajectory(
                    claim=c.inputs[1],
                    predicted=str(c.output),
                    expected=c.expected_output if isinstance(c.expected_output, list) else [str(c.expected_output)],
                    score=s,
                    context=batch[c.inputs[0]].context,
                )
                for c, s in zip(report.cases, scores)
            ]
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: EvaluationBatch[CARDSTrajectory, str],
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        records = []
        for traj in eval_batch.trajectories or []:
            if traj.score < 1.0:
                records.append(
                    {
                        "Inputs": {"claim": traj.claim},
                        "Generated Outputs": {"predicted": traj.predicted},
                        "Feedback": (f"Wrong — predicted '{traj.predicted}' but expected one of {traj.expected}."),
                    }
                )
        return {"instructions": records}


def build_mixed_trainval(mix: Mapping[str, tuple[int, int]]) -> tuple[Dataset, Dataset]:
    """Build combined train/validation datasets from a per-source ``(train_n, val_n)`` mix.

    Lets optimization be aimed at the same multi-dataset mix used for
    benchmarking (nslp / cs_v1 / cs_v2), rather than a fixed pair hard-coded
    into the script — pass whichever counts reflect the target evaluation mix.

    For each named dataset, the first ``train_n`` cases go to training and the
    *next* ``val_n`` cases (i.e. ``cases[train_n : train_n + val_n]``) go to
    validation, so the two slices are disjoint by construction. This matters:
    calling a dataset factory twice with two different ``limit`` values (e.g.
    ``climatesense_dataset_v1(limit=80)`` and ``climatesense_dataset_v1(limit=20)``)
    both start at row 0, so the "held-out" validation set would actually be a
    subset of the training data and GEPA's candidate-selection scores would be
    measuring train-set fit, not generalization.

    Args:
        mix: Mapping of dataset name (``"nslp"``, ``"cs_v1"``, or ``"cs_v2"``)
            to ``(train_n, val_n)`` case counts. Omit a name or pass
            ``(0, 0)`` to exclude that dataset entirely.

    Returns:
        ``(trainset, valset)`` — combined Datasets ready for :func:`optimize_prompt`.
    """
    from climafactskg.classifiers.cards.datasets import (
        climatesense_dataset_v1,
        climatesense_dataset_v2,
        nslp_dataset,
    )

    factories: dict[str, Any] = {
        "nslp": nslp_dataset,
        "cs_v1": climatesense_dataset_v1,
        "cs_v2": climatesense_dataset_v2,
    }

    train_cases = []
    val_cases = []
    for name, (train_n, val_n) in mix.items():
        if train_n <= 0 and val_n <= 0:
            continue
        if name not in factories:
            raise ValueError(f"Unknown dataset '{name}'. Choose from: {sorted(factories)}")
        cases = factories[name]().cases
        train_slice = cases[:train_n]
        val_slice = cases[train_n : train_n + val_n]
        logger.info(
            "Dataset '%s': %d train / %d val (%d available)",
            name,
            len(train_slice),
            len(val_slice),
            len(cases),
        )
        train_cases.extend(train_slice)
        val_cases.extend(val_slice)

    return Dataset(cases=train_cases), Dataset(cases=val_cases)


def _dataset_to_examples(dataset: Dataset) -> list[CARDSDataInst]:
    """Convert a pydantic-evals Dataset to a list of CARDSDataInst instances."""
    from .datasets import CARDSInput

    return [
        CARDSDataInst(
            claim=case.inputs.text if isinstance(case.inputs, CARDSInput) else str(case.inputs),
            expected=case.expected_output if isinstance(case.expected_output, list) else [str(case.expected_output)],
            context=case.inputs.context if isinstance(case.inputs, CARDSInput) else None,
        )
        for case in dataset.cases
    ]


def optimize_prompt(
    classifier: CARDSLLMClassifier,
    *,
    trainset: Dataset,
    valset: Dataset | None = None,
    max_metric_calls: int = 200,
    reflection_provider: str = "openrouter",
    reflection_model: str = "openai/gpt-4o-mini",
    save_path: str | None = None,
) -> str:
    """Optimize the system prompt of a classifier using GEPA.

    Mirrors :func:`.evaluate`: accepts a fully-configured
    :class:`CARDSLLMClassifier` (built via ``from_preset``) and all its model
    settings are used as-is.  GEPA proposes mutations to the system prompt and
    scores them via :class:`CARDSEvalsAdapter`.

    Args:
        classifier: Classifier to optimize.  Its current system prompt is used
            as the seed candidate.  Build it with
            ``CARDSLLMClassifier.from_preset(...)``.
        trainset: Dataset used for GEPA training evaluations.
        valset: Optional held-out validation dataset.  When ``None``, GEPA
            uses ``trainset`` for both training and validation.
        max_metric_calls: GEPA evaluation budget (number of classifier calls).
        reflection_provider: Provider for the GEPA reflection LM (uses
            pydantic-ai via :func:`.llm.classifier._build_pydantic_ai_model`).
        reflection_model: Model for the GEPA reflection LM.
        save_path: Optional file path to write the best prompt to after optimization.
            Useful for persisting results across runs.

    Returns:
        The best-performing system prompt string found by GEPA.
    """
    from pydantic_ai import Agent

    logger.info(
        "Optimizing classifier '%s/%s' (train=%d, val=%s, budget=%d)",
        classifier._provider,
        classifier._model,
        len(list(trainset.cases)),
        len(list(valset.cases)) if valset else "same",
        max_metric_calls,
    )

    train_examples = _dataset_to_examples(trainset)
    val_examples = _dataset_to_examples(valset) if valset is not None else train_examples

    adapter = CARDSEvalsAdapter(classifier)

    # Reflection agent — same two-liner pattern as CARDSLLMClassifier.__init__
    r_model = _build_pydantic_ai_model(reflection_provider, reflection_model)
    r_agent: Agent[None, str] = Agent(r_model, output_type=str)
    reflection_callable = lambda prompt: r_agent.run_sync(  # noqa: E731
        prompt if isinstance(prompt, str) else str(prompt)
    ).output

    result = optimize(
        seed_candidate={"instructions": classifier._system_prompt},
        trainset=train_examples,
        valset=val_examples,
        adapter=adapter,
        reflection_lm=reflection_callable,
        reflection_prompt_template=_SELF_CONTAINED_REFLECTION_PROMPT_TEMPLATE,
        max_metric_calls=max_metric_calls,
    )

    best: str = result.best_candidate["instructions"]
    logger.info("Optimization complete. Val scores: %s", result.val_aggregate_scores)
    if save_path is not None:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(best)
        logger.info("Best prompt saved to %s", save_path)
    return best


def _parse_mix_arg(spec: str) -> tuple[int, int]:
    """Parse a ``"train:val"`` CLI argument into an ``(train_n, val_n)`` pair."""
    train_str, _, val_str = spec.partition(":")
    return int(train_str), int(val_str or 0)


if __name__ == "__main__":
    import argparse
    import logging as _logging

    from climafactskg.classifiers.cards.datasets import (
        climatesense_dataset_v1,
        climatesense_dataset_v2,
        nslp_dataset,
    )
    from climafactskg.classifiers.cards.eval import benchmark_configs
    from climafactskg.classifiers.cards.llm.prompts import CARDS_SEED_PROMPT

    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    _parser = argparse.ArgumentParser(description=__doc__)
    _parser.add_argument(
        "--nslp",
        type=_parse_mix_arg,
        default=(80, 20),
        metavar="TRAIN:VAL",
        help="nslp train/val case counts (default: 80:20).",
    )
    _parser.add_argument(
        "--cs-v1",
        type=_parse_mix_arg,
        default=(80, 20),
        metavar="TRAIN:VAL",
        help="climatesense_dataset_v1 train/val case counts (default: 80:20).",
    )
    _parser.add_argument(
        "--cs-v2",
        type=_parse_mix_arg,
        default=(80, 20),
        metavar="TRAIN:VAL",
        help="climatesense_dataset_v2 train/val case counts (default: 80:20).",
    )
    _parser.add_argument("--max-metric-calls", type=int, default=200, help="GEPA evaluation budget (default: 200).")
    _parser.add_argument(
        "--reflection-model", default="openai/gpt-4o-mini", help="Reflection LM model (default: openai/gpt-4o-mini)."
    )
    _parser.add_argument(
        "--reflection-provider", default="openrouter", help="Reflection LM provider (default: openrouter)."
    )
    _parser.add_argument("--save-path", default="data/optimised_prompt.txt", help="Where to save the best prompt.")
    _args = _parser.parse_args()

    # Sourcing train/val from the same three datasets used for benchmarking
    # (nslp / cs_v1 / cs_v2), with the mix parametrized per-source rather than
    # hard-coded, so optimization can be aimed at whatever blend of the
    # evaluation datasets matters most — e.g. weight cs_v1/cs_v2 (the
    # project's own annotations) higher than nslp, or vice versa.
    _train, _val = build_mixed_trainval(
        {
            "nslp": _args.nslp,
            "cs_v1": _args.cs_v1,
            "cs_v2": _args.cs_v2,
        }
    )

    clf = CARDSLLMClassifier.from_preset(
        "climatesense-nslp",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        system_prompt=CARDS_SEED_PROMPT,
        use_preclassifier=False,
        cache_path="data/eval_cache_seed.db",
        default_concurrency=8,
    )

    best_prompt = optimize_prompt(
        clf,
        trainset=_train,
        valset=_val,
        max_metric_calls=_args.max_metric_calls,
        reflection_provider=_args.reflection_provider,
        reflection_model=_args.reflection_model,
        save_path=_args.save_path,
    )
    print("Original prompt:\n", clf._system_prompt)
    print("\nOptimised prompt:\n", best_prompt)

    optimised_clf = CARDSLLMClassifier.from_preset(
        "climatesense-nslp",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        system_prompt=best_prompt,
        use_preclassifier=False,
        cache_path="data/eval_cache_optimised.db",
        default_concurrency=8,
    )

    results = benchmark_configs(
        configs={"original": clf, "optimised": optimised_clf},
        datasets={
            "nslp": nslp_dataset(),
            "cs_v1": climatesense_dataset_v1(),
            "cs_v2": climatesense_dataset_v2(),
        },
    )
    print(results.to_string(index=False))
