"""CARDS classifier evaluation — runner and benchmarking utilities.

This module is the main entry point for evaluating CARDS classifiers.  It
re-exports all public symbols from :mod:`.evaluators` and :mod:`.datasets` so
that existing ``from climafactskg.classifiers.cards.eval import ...`` imports
continue to work without change.

Per-case evaluators
-------------------
CARDSOneOfMatch
    Exact match: 1.0 if prediction ∈ gold set.

CARDSHierarchicalMatch
    Partial-credit hF1 against the best-matching gold label.

Aggregate report evaluators
----------------------------
MultiMetricsReportEvaluator
    Macro / micro / weighted precision, recall, and F1 via scikit-learn.

HierarchicalMetricsReportEvaluator
    Mean exact-match rate and mean hF1.

DepthMetricsReportEvaluator
    P / R / F1 at taxonomy depths 1 and 2.

Dataset factories
-----------------
nslp_dataset
    NSLP / ClimateCheck claims from HuggingFace.

climatesense_dataset_v1
    ClimateSense internal annotation round 1.

climatesense_dataset_v2
    ClimateSense internal annotation round 2.

Runners
-------
evaluate
    Single-classifier evaluation with full per-case tables printed to the console.

benchmark_configs
    Grid evaluation over a dict of configs × dict of datasets; returns a tidy
    summary DataFrame.
"""

import logging
from typing import Any, Literal, cast

import pandas as pd
from pydantic_evals import Dataset
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from sklearn.metrics import precision_recall_fscore_support

# Re-export dataset factories and CARDSInput
from .datasets import (  # noqa: F401
    CARDSInput,
    _download_annotations_df,
    _hierarchical_majority_vote,
    _load_climatesense_dataset,
    climatesense_dataset_v1,
    climatesense_dataset_v2,
    nslp_dataset,
)

# Re-export evaluators so callers can do ``from .eval import CARDSOneOfMatch`` etc.
from .evaluators import (  # noqa: F401
    _MAX_CLASSIFIER_DEPTH,
    CARDSHierarchicalMatch,
    CARDSOneOfMatch,
    DepthMetricsReportEvaluator,
    HierarchicalMetricsReportEvaluator,
    MultiMetricsReportEvaluator,
    _hierarchical_f1,
    ancestors_of,
    project_to_depth,
)

logger = logging.getLogger(__name__)

_console = Console()


def _prompt_id(classifier, max_chars: int = 60) -> str:
    """Return a short prompt identifier: first non-empty line of the system prompt, truncated."""
    prompt = getattr(classifier, "_system_prompt", None) or ""
    first_line = next((ln for ln in prompt.splitlines() if ln.strip()), prompt)
    return first_line[:max_chars] + ("…" if len(first_line) > max_chars else "")


def evaluate(classifier, dataset: Dataset):
    """Evaluate a CARDS classifier against a pydantic-evals Dataset.

    Predictions are collected via :meth:`classify_batch` (when available) or
    sequential :meth:`classify` calls, then scored against ground-truth labels.
    All registered evaluators and report evaluators on the dataset are run, and
    their tables are printed to the console.

    Works with any classifier that exposes a ``classify(text: str) -> str``
    method (or optionally ``classify_batch(texts: list[str]) -> list[str]``).

    Args:
        classifier: Classifier instance with ``classify`` / ``classify_batch``.
        dataset: A pydantic-evals :class:`Dataset`, e.g. from :func:`nslp_dataset`.

    Returns:
        The pydantic-evals :class:`EvaluationReport` (per-case scores for all
        registered evaluators).
    """
    cases = list(dataset.cases)
    inputs = [case.inputs for case in cases]
    texts = [inp.text if isinstance(inp, CARDSInput) else inp for inp in inputs]
    contexts = [inp.context if isinstance(inp, CARDSInput) else None for inp in inputs]
    classifier_name = type(classifier).__name__
    logger.info("Starting evaluation: %s on '%s' (%d cases)", classifier_name, dataset.name, len(cases))

    if hasattr(classifier, "classify_batch"):
        logger.info("Running classify_batch")
        if any(contexts) and hasattr(classifier, "_user_prompt_with_context"):
            preds = classifier.classify_batch(texts, contexts=contexts)
        else:
            preds = classifier.classify_batch(texts)
    else:
        from rich.progress import track

        logger.info("Running sequential classify")
        use_context = any(contexts) and hasattr(classifier, "_user_prompt_with_context")
        preds = [
            classifier.classify(t, context=ctx) if use_context else classifier.classify(t)
            for t, ctx in track(zip(texts, contexts), description="Classifying...", total=len(texts))
        ]

    logger.info("Predictions complete — running pydantic-evals scoring")

    from pydantic_evals.reporting import _render_analysis
    from rich.columns import Columns

    provider = getattr(classifier, "_provider", None)
    model = getattr(classifier, "_model", classifier_name)
    identity = f"{model} ({provider})" if provider else model
    _console.print(Rule(f"{identity}  |  {_prompt_id(classifier)}  |  {len(cases)} cases"))

    unique_labels = sorted(set(preds))
    logger.info("Predicted label set (%d unique): %s", len(unique_labels), unique_labels)
    _console.print(f"Predicted labels ({len(unique_labels)} unique):", Columns(unique_labels))

    cache = {(t, c): p for t, c, p in zip(texts, contexts, preds, strict=True)}
    report = dataset.evaluate_sync(
        lambda inp, _c=cache: _c[(inp.text, inp.context) if isinstance(inp, CARDSInput) else (str(inp), None)]
    )

    logger.info("Rendering report analyses (%d)", len(report.analyses))
    for analysis in report.analyses:
        _console.print(_render_analysis(analysis))

    logger.info("Evaluation complete: %s on '%s'", classifier_name, dataset.name)
    return report


def benchmark_configs(
    configs: dict[str, Any],
    datasets: dict[str, Dataset],
) -> pd.DataFrame:
    """Evaluate multiple classifier configs across multiple datasets.

    Runs every (config, dataset) combination, collects per-case scores, and
    returns a tidy summary DataFrame with one row per combination.  Per-case
    tables are suppressed; use :func:`evaluate` directly when you need them.

    Args:
        configs: Mapping of config label → classifier instance (any object with
            ``classify(text) -> str`` or ``classify_batch(texts) -> list[str]``).
        datasets: Mapping of dataset label → pydantic-evals :class:`Dataset`.

    Returns:
        DataFrame with columns ``config``, ``dataset``, ``n_cases``,
        ``exact_match``, ``h_f1``, ``macro_f1``, ``micro_f1``, ``weighted_f1``.

    Example::

        results = benchmark_configs(
            configs={"gpt4o": clf1, "qwen3": clf2},
            datasets={
                "nslp":  nslp_dataset(limit=200),
                "cs_v1": climatesense_dataset_v1(),
                "cs_v2": climatesense_dataset_v2(),
            },
        )
        print(results.to_string(index=False))
    """
    from rich.progress import track

    rows = []
    combos = [(cn, dn, clf, ds) for cn, clf in configs.items() for dn, ds in datasets.items()]
    for config_name, dataset_name, classifier, dataset in track(combos, description="Benchmarking..."):
        logger.info("Benchmarking '%s' on '%s'", config_name, dataset_name)
        cases = list(dataset.cases)
        inputs = [case.inputs for case in cases]
        texts = [inp.text if isinstance(inp, CARDSInput) else inp for inp in inputs]
        contexts = [inp.context if isinstance(inp, CARDSInput) else None for inp in inputs]

        try:
            if hasattr(classifier, "classify_batch"):
                if any(contexts) and hasattr(classifier, "_user_prompt_with_context"):
                    preds = classifier.classify_batch(texts, contexts=contexts)
                else:
                    preds = classifier.classify_batch(texts)
            else:
                use_context = any(contexts) and hasattr(classifier, "_user_prompt_with_context")
                preds = [
                    classifier.classify(t, context=ctx) if use_context else classifier.classify(t)
                    for t, ctx in zip(texts, contexts)
                ]
        except Exception as exc:
            logger.warning("Failed '%s' on '%s': %s", config_name, dataset_name, exc)
            rows.append(
                {
                    "config": config_name,
                    "dataset": dataset_name,
                    "provider": getattr(classifier, "_provider", "—"),
                    "model": getattr(classifier, "_model", type(classifier).__name__),
                    "prompt": _prompt_id(classifier),
                    "n_cases": 0,
                    "exact_match": float("nan"),
                    "h_f1": float("nan"),
                    "d1_macro_f1": float("nan"),
                    "d1_weighted_f1": float("nan"),
                    "d2_macro_f1": float("nan"),
                    "d2_weighted_f1": float("nan"),
                    "macro_f1": float("nan"),
                    "micro_f1": float("nan"),
                    "weighted_f1": float("nan"),
                    "error": str(exc),
                }
            )
            continue

        cache = {(t, c): p for t, c, p in zip(texts, contexts, preds, strict=True)}
        report = dataset.evaluate_sync(
            lambda inp, _c=cache: _c[(inp.text, inp.context) if isinstance(inp, CARDSInput) else (str(inp), None)]
        )

        exact_scores: list[float] = []
        hier_scores: list[float] = []
        y_true: list[str] = []
        y_pred: list[str] = []
        true_classes: set[str] = set()

        for case in report.cases:
            if case.output is None or case.expected_output is None:
                continue
            predicted = str(case.output)
            exp_out = case.expected_output
            expected = [str(exp_out)] if isinstance(exp_out, str) else [str(e) for e in exp_out]
            true_classes.update(expected)

            one_of_score = case.scores.get("CARDSOneOfMatch")
            if one_of_score is not None:
                exact_scores.append(one_of_score.value)
            if (h := case.scores.get("CARDSHierarchicalMatch")) is not None:
                hier_scores.append(h.value)

            if one_of_score is not None and one_of_score.value == 1.0:
                y_true.append(predicted)
            else:
                a_pred = ancestors_of(predicted)
                charged = max(expected, key=lambda e: _hierarchical_f1(a_pred, ancestors_of(e)))
                y_true.append(charged)
            y_pred.append(predicted)

        f1_by_strategy: dict[str, float] = {}
        d1_f1_by_strategy: dict[str, float] = {}
        if y_true and true_classes:
            gold_labels = sorted(true_classes)
            for strategy in ("macro", "micro", "weighted"):
                _, _, f1, _ = precision_recall_fscore_support(
                    y_true,
                    y_pred,
                    average=cast(Literal["binary", "micro", "macro", "samples", "weighted"], strategy),
                    labels=gold_labels,
                    zero_division=0,
                )
                f1_by_strategy[strategy] = float(f1)

            d1_true = [project_to_depth(t, 1) for t in y_true]
            d1_pred = [project_to_depth(p, 1) for p in y_pred]
            d1_labels = sorted({project_to_depth(t, 1) for t in true_classes})
            for strategy in ("macro", "weighted"):
                _, _, f1, _ = precision_recall_fscore_support(
                    d1_true,
                    d1_pred,
                    average=cast(Literal["binary", "micro", "macro", "samples", "weighted"], strategy),
                    labels=d1_labels,
                    zero_division=0,
                )
                d1_f1_by_strategy[strategy] = float(f1)

        rows.append(
            {
                "config": config_name,
                "dataset": dataset_name,
                "provider": getattr(classifier, "_provider", "—"),
                "model": getattr(classifier, "_model", type(classifier).__name__),
                "prompt": _prompt_id(classifier),
                "n_cases": len(y_pred),
                "exact_match": round(sum(exact_scores) / len(exact_scores), 4) if exact_scores else 0.0,
                "h_f1": round(sum(hier_scores) / len(hier_scores), 4) if hier_scores else 0.0,
                "d1_macro_f1": round(d1_f1_by_strategy.get("macro", 0.0), 4),
                "d1_weighted_f1": round(d1_f1_by_strategy.get("weighted", 0.0), 4),
                "d2_macro_f1": round(f1_by_strategy.get("macro", 0.0), 4),
                "d2_weighted_f1": round(f1_by_strategy.get("weighted", 0.0), 4),
                "macro_f1": round(f1_by_strategy.get("macro", 0.0), 4),
                "micro_f1": round(f1_by_strategy.get("micro", 0.0), 4),
                "weighted_f1": round(f1_by_strategy.get("weighted", 0.0), 4),
                "error": "",
            }
        )
        logger.info(
            "  exact=%.4f  h_f1=%.4f  macro_f1=%.4f",
            rows[-1]["exact_match"],
            rows[-1]["h_f1"],
            rows[-1]["macro_f1"],
        )

    return pd.DataFrame(rows)


def print_benchmark(df: pd.DataFrame, title: str = "Benchmark Results") -> None:
    """Render a benchmark DataFrame as a rich table.

    Designed for DataFrames returned by :func:`benchmark_configs`.  Columns
    absent from *df* are silently skipped, so the function works with any
    subset of the enriched frame.
    """
    # (key, header, style, justify, max_width, no_wrap)
    # macro_f1/micro_f1/weighted_f1 are omitted — d2_* carry the same values.
    col_spec: list[tuple[str, str, str, str, int | None, bool]] = [
        ("config", "Config", "bold cyan", "left", 22, True),
        ("dataset", "Dataset", "", "left", 16, True),
        ("provider", "Provider", "dim", "left", 12, True),
        ("model", "Model", "", "left", 22, True),
        ("prompt", "Prompt", "dim italic", "left", 35, True),
        ("n_cases", "N", "", "right", None, False),
        ("exact_match", "Exact", "green", "right", None, False),
        ("h_f1", "hF1", "green", "right", None, False),
        ("d1_macro_f1", "D1 Mac", "yellow", "right", None, False),
        ("d1_weighted_f1", "D1 Wt", "yellow", "right", None, False),
        ("d2_macro_f1", "D2 Mac", "magenta", "right", None, False),
        ("d2_weighted_f1", "D2 Wt", "magenta", "right", None, False),
        ("error", "Error", "bold red", "left", 30, True),
    ]

    table = Table(title=title, show_lines=True)
    present = [(col, hdr, style, just, mw, nw) for col, hdr, style, just, mw, nw in col_spec if col in df.columns]
    for _, hdr, style, just, mw, nw in present:
        justify_val = cast(Literal["left", "right", "center", "full", "default"], just)
        table.add_column(hdr, style=style or None, justify=justify_val, max_width=mw, no_wrap=nw, overflow="ellipsis")

    for _, row in df.iterrows():
        cells = []
        for col, _, _, _, _, _ in present:
            val = row[col]
            if isinstance(val, float):
                cells.append(f"{val:.4f}")
            else:
                cells.append(str(val))
        table.add_row(*cells)

    _console.print(table)


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from climafactskg.classifiers.cards.llm.classifier import CARDSLLMClassifier

    def _clf(preset: str, model: str, concurrency: int = 8, **kw) -> CARDSLLMClassifier:
        return CARDSLLMClassifier.from_preset(
            preset,
            provider="openrouter",
            model=model,
            use_preclassifier=False,
            cache_path="data/eval_cache.db",
            default_concurrency=concurrency,
            **kw,
        )

    _greedy = {"temperature": 0.0, "top_p": None, "max_tokens": None}

    configs = {
        # --- prompt comparison (gpt-4o-mini, three presets) ---
        "gpt-4o-mini | climatesense": _clf("climatesense-nslp", "openai/gpt-4o-mini"),
        "gpt-4o-mini | xplainnlp": _clf("xplainnlp-nslp", "openai/gpt-4o-mini", **_greedy),
        "gpt-4o-mini | narrative": _clf("cards-narrative", "openai/gpt-4o-mini"),
        # --- model comparison (xplainnlp preset) ---
        # closed — expensive
        "gpt-5.2 | xplainnlp": _clf("xplainnlp-nslp", "openai/gpt-5.2", **_greedy),
        # open-weight — OpenAI OSS 120B
        "gpt-oss-120b | xplainnlp": _clf("xplainnlp-nslp", "openai/gpt-oss-120b", **_greedy),
        # open-weight — frontier MoE (284B/13B active, 1M context, current top-adoption
        # open-weight model on OpenRouter, cheaper per-token than qwen3.6-35b-a3b).
        # Lower concurrency: high demand means its upstream OpenRouter backend
        # providers (Fireworks, WandB, AkashML, DeepInfra) rate-limit quickly under
        # concurrency=8, which can cascade into fallback-provider errors.
        "deepseek-v4-flash | xplainnlp": _clf("xplainnlp-nslp", "deepseek/deepseek-v4-flash", concurrency=2, **_greedy),
        # open-weight — large dense
        "llama-3.3-70b | xplainnlp": _clf("xplainnlp-nslp", "meta-llama/llama-3.3-70b-instruct", **_greedy),
        # open-weight — OpenAI OSS 20B
        "gpt-oss-20b | xplainnlp": _clf("xplainnlp-nslp", "openai/gpt-oss-20b", **_greedy),
        # open-weight — small MoE (3B active / 35B total, very cheap)
        "qwen3.6-35b | xplainnlp": _clf("xplainnlp-nslp", "qwen/qwen3.6-35b-a3b", **_greedy),
        # open-weight — tiny
        "llama-3.1-8b | xplainnlp": _clf("xplainnlp-nslp", "meta-llama/llama-3.1-8b-instruct", **_greedy),
        # No Gemma entry: verified against OpenRouter's live /api/v1/models catalog and no
        # "gemma" model is currently listed there at all — the "Gemma 4" model info found via
        # web search was wrong (unreliable third-party sites), confirmed by 100% failed runs.
        # --- Qwen3 (keep original thinking-mode temperature/top_p/max_tokens) ---
        # "qwen3-8b | xplainnlp": _clf("xplainnlp-nslp", "qwen/qwen3-8b:nitro"),
    }

    datasets = {
        "nslp": nslp_dataset(),
        "climatesense_v1": climatesense_dataset_v1(),
        "climatesense_v2": climatesense_dataset_v2(),
    }

    results = benchmark_configs(configs, datasets)
    print_benchmark(results)
