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
from collections.abc import Sequence
from typing import Any, Literal, cast

import pandas as pd
from pydantic_evals import Dataset
from rich import box
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from sklearn.metrics import precision_recall_fscore_support

from .base import CARDSClassifierBase

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
from .runs import CASE_COLUMNS, BenchmarkRun, bootstrap_ci, collect_meta, context_effect, save_run

logger = logging.getLogger(__name__)

_console = Console()


def _prompt_id(classifier, max_chars: int = 60) -> str:
    """Return a short prompt identifier: first non-empty line of the system prompt, truncated."""
    prompt = getattr(classifier, "_system_prompt", None) or ""
    first_line = next((ln for ln in prompt.splitlines() if ln.strip()), prompt)
    return first_line[:max_chars] + ("…" if len(first_line) > max_chars else "")


def evaluate(classifier, dataset: Dataset, use_context: bool = True):
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
        use_context: When ``False``, ignore every case's ``context`` and classify the claim text alone (the gold
            labels are claim-only annotations, so this is the like-for-like run). Defaults to ``True``: contexts
            are used when present and the classifier supports them.

    Returns:
        The pydantic-evals :class:`EvaluationReport` (per-case scores for all
        registered evaluators).
    """
    cases = list(dataset.cases)
    inputs = [case.inputs for case in cases]
    texts = [inp.text if isinstance(inp, CARDSInput) else inp for inp in inputs]
    contexts = [inp.context if isinstance(inp, CARDSInput) else None for inp in inputs]
    # `contexts` (the dataset's own) keys the prediction lookup below; `predict_contexts` is what the classifier sees.
    predict_contexts = contexts if use_context else [None] * len(texts)
    # All three CARDS engines (CARDSClassifierBase subclasses) accept `context`
    # via classify/classify_batch. Duck-typed classifiers that don't inherit it
    # (arbitrary external `classify(text) -> str` objects, per this function's
    # docstring) fall back to plain text — passing `context=` to something that
    # doesn't accept it would raise a TypeError.
    supports_context = isinstance(classifier, CARDSClassifierBase)
    if use_context and supports_context and any(contexts):
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")
    classifier_name = type(classifier).__name__
    logger.info("Starting evaluation: %s on '%s' (%d cases)", classifier_name, dataset.name, len(cases))
    if hasattr(classifier, "classify_batch"):
        logger.info("Running classify_batch")
        if any(predict_contexts) and supports_context:
            preds = classifier.classify_batch(texts, contexts=predict_contexts)
        else:
            preds = classifier.classify_batch(texts)
    else:
        from rich.progress import track

        logger.info("Running sequential classify")
        pass_context = any(predict_contexts) and supports_context
        preds = [
            classifier.classify(t, context=ctx) if pass_context else classifier.classify(t)
            for t, ctx in track(
                zip(texts, predict_contexts, strict=True), description="Classifying...", total=len(texts)
            )
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
    context_modes: Sequence[Literal["none", "with"]] = ("none", "with"),
    min_context_coverage: float = 0.5,
    save_dir: str | None = None,
) -> pd.DataFrame:
    """Evaluate multiple classifier configs across multiple datasets.

    Runs every (config, dataset) combination, collects per-case scores, and
    returns a tidy summary DataFrame with one row per combination.  Per-case
    tables are suppressed; use :func:`evaluate` directly when you need them.

    Args:
        configs: Mapping of config label → classifier instance (any object with
            ``classify(text) -> str`` or ``classify_batch(texts) -> list[str]``).
        datasets: Mapping of dataset label → pydantic-evals :class:`Dataset`.
        context_modes: Which context modes to run per (config, dataset). ``"none"`` classifies the claim text alone;
            ``"with"`` also passes each case's review context and is skipped for datasets that have none.
        min_context_coverage: A ``"with"`` run on a dataset where fewer than this fraction of cases carry context logs
            a warning: its result mostly reflects claim-only classification. Compare on the covered subset instead
            (load the dataset with ``only_with_context=True``).
        save_dir: When set, the run (metadata, tidy per-case rows and the summary) is saved to a new timestamped
            directory under it (see :mod:`.runs`) and its path is attached as ``df.attrs["run_dir"]``. A failed
            save logs a warning and never loses the returned DataFrame.

    Returns:
        DataFrame with columns ``config``, ``dataset``, ``context``, ``n_with_context`` (cases that actually
            carried context in that run), ``n_cases``,
        ``exact_match``, ``h_f1``, ``macro_f1``, ``micro_f1``, ``weighted_f1`` and the 95% bootstrap intervals
        ``exact_lo``/``exact_hi`` and ``h_f1_lo``/``h_f1_hi``.

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
    case_rows: list[dict[str, Any]] = []
    combos = [
        (cn, dn, clf, ds, mode) for cn, clf in configs.items() for dn, ds in datasets.items() for mode in context_modes
    ]
    for config_name, dataset_name, classifier, dataset, mode in track(combos, description="Benchmarking..."):
        logger.info("Benchmarking '%s' on '%s' (context=%s)", config_name, dataset_name, mode)
        cases = list(dataset.cases)
        inputs = [case.inputs for case in cases]
        texts = [inp.text if isinstance(inp, CARDSInput) else inp for inp in inputs]
        contexts = [inp.context if isinstance(inp, CARDSInput) else None for inp in inputs]
        if mode == "with" and not any(contexts):
            logger.info("Skipping context mode 'with' for '%s': dataset has no context", dataset_name)
            continue
        predict_contexts = contexts if mode == "with" else [None] * len(texts)
        n_context = sum(1 for c in contexts if c)
        if mode == "with" and n_context / len(contexts) < min_context_coverage:
            logger.warning(
                "Context mode 'with' on '%s': only %d of %d cases carry context, so the result mostly reflects "
                "claim-only classification; compare on the covered subset with only_with_context=True",
                dataset_name,
                n_context,
                len(contexts),
            )

        supports_context = isinstance(classifier, CARDSClassifierBase)
        try:
            if hasattr(classifier, "classify_batch"):
                if any(predict_contexts) and supports_context:
                    preds = classifier.classify_batch(texts, contexts=predict_contexts)
                else:
                    preds = classifier.classify_batch(texts)
            else:
                pass_context = any(predict_contexts) and supports_context
                preds = [
                    classifier.classify(t, context=ctx) if pass_context else classifier.classify(t)
                    for t, ctx in zip(texts, predict_contexts, strict=True)
                ]
        except Exception as exc:
            logger.warning("Failed '%s' on '%s': %s", config_name, dataset_name, exc)
            rows.append(
                {
                    "config": config_name,
                    "dataset": dataset_name,
                    "context": mode,
                    "n_with_context": sum(1 for c in predict_contexts if c),
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
                    "exact_lo": float("nan"),
                    "exact_hi": float("nan"),
                    "h_f1_lo": float("nan"),
                    "h_f1_hi": float("nan"),
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
            h = case.scores.get("CARDSHierarchicalMatch")
            if h is not None:
                hier_scores.append(h.value)

            if one_of_score is not None and one_of_score.value == 1.0:
                y_true.append(predicted)
            else:
                a_pred = ancestors_of(predicted)
                charged = max(expected, key=lambda e: _hierarchical_f1(a_pred, ancestors_of(e)))
                y_true.append(charged)
            y_pred.append(predicted)
            case_rows.append(
                {
                    "config": config_name,
                    "dataset": dataset_name,
                    "context": mode,
                    "case_id": case.name,
                    "text": case.inputs.text if isinstance(case.inputs, CARDSInput) else str(case.inputs),
                    "gold": ";".join(expected),
                    "pred": predicted,
                    "exact": one_of_score.value if one_of_score is not None else float("nan"),
                    "hf1": h.value if h is not None else float("nan"),
                    "has_context": isinstance(case.inputs, CARDSInput) and bool(case.inputs.context),
                    "gold_d1": project_to_depth(y_true[-1], 1),
                    "pred_d1": project_to_depth(predicted, 1),
                }
            )

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
                "context": mode,
                "n_with_context": sum(1 for c in predict_contexts if c),
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
                "exact_lo": (ci_exact := bootstrap_ci(exact_scores))[0],
                "exact_hi": ci_exact[1],
                "h_f1_lo": (ci_hier := bootstrap_ci(hier_scores))[0],
                "h_f1_hi": ci_hier[1],
                "error": "",
            }
        )
        logger.info(
            "  exact=%.4f  h_f1=%.4f  macro_f1=%.4f",
            rows[-1]["exact_match"],
            rows[-1]["h_f1"],
            rows[-1]["macro_f1"],
        )

    df = pd.DataFrame(rows)
    if save_dir is not None:
        try:
            configs_meta = [
                {
                    "label": name,
                    "provider": str(getattr(clf, "_provider", "")),
                    "model": str(getattr(clf, "_model", type(clf).__name__)),
                    "prompt": _prompt_id(clf),
                }
                for name, clf in configs.items()
            ]
            run = BenchmarkRun(
                meta=collect_meta(datasets, context_modes, min_context_coverage, configs_meta),
                summary=df,
                cases=pd.DataFrame(case_rows, columns=list(CASE_COLUMNS)),
            )
            df.attrs["run_dir"] = str(save_run(run, save_dir))
        except OSError as exc:
            logger.warning("Could not save benchmark run to %s: %s", save_dir, exc)
    return df


# Score columns must never be squeezed (a truncated "0.…" is useless); the text columns give way instead.
_MIN_WIDTHS = {"exact_match": 10, "h_f1": 10, "d1_macro_f1": 6, "d2_macro_f1": 6, "n_cases": 3, "n_with_context": 3}
_COMPACT_COLUMNS = (
    "config",
    "dataset",
    "context",
    "n_with_context",
    "n_cases",
    "exact_match",
    "h_f1",
    "d1_macro_f1",
    "d2_macro_f1",
)
# Metric columns that show a dash when nothing was evaluated (n_cases == 0), never a made-up 0.000.
_METRIC_COLUMNS = ("exact_match", "h_f1", "d1_macro_f1", "d1_weighted_f1", "d2_macro_f1", "d2_weighted_f1")


def _score_cell(row: pd.Series, col: str) -> str:
    """A score as ``0.378±0.08`` (value ± half-width of its interval), ``0.378`` without one, or ``—``."""
    value = row[col]
    if pd.isna(value):
        return "—"
    lo, hi = row.get(f"{col.replace('exact_match', 'exact')}_lo"), row.get(f"{col.replace('exact_match', 'exact')}_hi")
    if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
        return f"{value:.3f}"
    return f"{value:.3f}±{(hi - lo) / 2:.2f}"


def print_benchmark(df: pd.DataFrame, title: str = "Benchmark Results", wide: bool = False) -> None:
    """Render a benchmark DataFrame as a rich table.

    The default compact view keeps the columns that matter for comparing runs and fits 80 columns; scores show their
    95% bootstrap interval as ``value±half-width`` when the frame has interval columns. ``wide=True`` shows every
    column (provider, model, prompt, weighted F1). Columns absent from *df* are silently skipped.
    """
    # (key, header, style, justify, max_width, no_wrap)
    # macro_f1/micro_f1/weighted_f1 are omitted — d2_* carry the same values.
    col_spec: list[tuple[str, str, str, str, int | None, bool]] = [
        ("config", "Config", "bold cyan", "left", 22 if wide else 10, True),
        ("dataset", "Dataset", "", "left", 16 if wide else 8, True),
        ("context", "Ctx", "dim", "left", 4, True),
        ("n_with_context", "Ctx N", "dim", "right", None, False),
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
        ("error", "Error", "bold red", "left", 30 if wide else 12, True),
    ]

    table = Table(
        title=title,
        show_lines=wide,
        box=box.SQUARE if wide else box.SIMPLE,
        collapse_padding=not wide,
        pad_edge=wide,
    )
    # The compact view has no Error column (it cannot fit 80 columns next to the scores); failures are printed as
    # one line each under the table instead.
    present = [
        (col, hdr, style, just, mw, nw)
        for col, hdr, style, just, mw, nw in col_spec
        if col in df.columns and (wide or col in _COMPACT_COLUMNS)
    ]
    for col, hdr, style, just, mw, nw in present:
        justify_val = cast(Literal["left", "right", "center", "full", "default"], just)
        table.add_column(
            hdr,
            style=style or None,
            justify=justify_val,
            max_width=mw,
            min_width=_MIN_WIDTHS.get(col),
            no_wrap=nw,
            overflow="ellipsis",
        )

    for _, row in df.iterrows():
        cells = []
        no_cases = "n_cases" in df.columns and row["n_cases"] == 0
        for col, _, _, _, _, _ in present:
            if no_cases and col in _METRIC_COLUMNS:
                cells.append("—")
            elif col in ("exact_match", "h_f1"):
                cells.append(_score_cell(row, col))
            elif isinstance(row[col], float):
                cells.append("—" if pd.isna(row[col]) else f"{row[col]:.3f}")
            else:
                cells.append(str(row[col]))
        table.add_row(*cells)

    _console.print(table)
    if not wide and "error" in df.columns:
        for _, row in df.iterrows():
            error = "" if pd.isna(row["error"]) else str(row["error"]).strip()
            if error:
                label = (
                    f"{row['config']}/{row['dataset']}/{row['context']}" if "context" in df.columns else row["config"]
                )
                label = label if len(label) <= 30 else label[:29] + "…"  # keep room for the reason at 80 columns
                _console.print(f"[red]failed[/red] {label}: {error}", overflow="ellipsis", no_wrap=True, crop=True)
    if "context" in df.columns and (df["context"] == "with").any():
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")


def print_context_effect(cases: pd.DataFrame) -> None:
    """Print the paired none-vs-with context effect per (config, dataset) from a saved run's case rows."""
    effect = context_effect(cases)
    if effect.empty:
        _console.print("[dim]No cases carry context in both runs, so there is nothing to compare.[/dim]")
        return
    table = Table(
        title="Effect of context (same cases, exact match)", box=box.SIMPLE, collapse_padding=True, pad_edge=False
    )
    # (header, justify, max_width, min_width): the numbers keep their room, the label columns give way.
    for header, justify, max_width, min_width in (
        ("Config", "left", 14, None),
        ("Dataset", "left", 10, None),
        ("Paired", "right", None, 6),
        ("None", "right", None, 5),
        ("With", "right", None, 5),
        ("Δ", "right", None, 6),
        ("Fixed", "right", None, 5),
        ("Broken", "right", None, 6),
        ("Same", "right", None, 4),
    ):
        table.add_column(
            header,
            justify=cast(Literal["left", "right"], justify),
            max_width=max_width,
            min_width=min_width,
            no_wrap=True,
            overflow="ellipsis",
        )
    for _, row in effect.iterrows():
        table.add_row(
            str(row["config"]),
            str(row["dataset"]),
            str(int(row["n_paired"])),
            f"{row['exact_none']:.3f}",
            f"{row['exact_with']:.3f}",
            f"{row['delta']:+.3f}",
            str(int(row["fixed"])),
            str(int(row["broken"])),
            str(int(row["unchanged"])),
        )
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
