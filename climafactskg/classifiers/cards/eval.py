"""CARDS classifier evaluation: benchmarking, printing and the single-classifier shortcut.

``benchmark_configs`` evaluates a dict of classifier configs on a dict of datasets and returns a tidy summary DataFrame
(optionally saving the run, see :mod:`.runs`); ``climafactskg eval run`` drives it from a TOML config. ``evaluate`` is
the same thing for one classifier on one dataset. ``print_benchmark`` and ``print_context_effect`` render the results.

For convenience this module re-exports the per-case evaluators (:mod:`.evaluators`) and the dataset factories
(:mod:`.datasets`), so ``from climafactskg.classifiers.cards.eval import nslp_dataset`` keeps working.
"""

import logging
from collections.abc import Sequence
from typing import Any, Literal, cast

import pandas as pd
from pydantic_evals import Dataset
from rich import box
from rich.console import Console
from rich.table import Table

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
    _hierarchical_f1,
    ancestors_of,
    project_to_depth,
)
from .runs import (
    CASE_COLUMNS,
    BenchmarkRun,
    bootstrap_ci,
    collect_meta,
    context_effect,
    model_size_from_id,
    save_run,
)
from .scoring import (
    Metrics,
    bootstrap_macro_f1,
    case_scores,
    charged_gold,
    compute_metrics,
    detected_category_scores,
    is_not_climate_gold,
    normalize_gold,
    normalize_label,
    relatedness,
)

logger = logging.getLogger(__name__)

_console = Console()


def _prompt_id(classifier, max_chars: int = 60) -> str:
    """Return a short prompt identifier: first non-empty line of the system prompt, truncated."""
    prompt = getattr(classifier, "_system_prompt", None) or ""
    first_line = next((ln for ln in prompt.splitlines() if ln.strip()), prompt)
    return first_line[:max_chars] + ("…" if len(first_line) > max_chars else "")


def evaluate(
    classifier,
    dataset: Dataset,
    use_context: bool = True,
    category_scores: Literal["all", "narrative_only"] = "all",
) -> pd.DataFrame:
    """Evaluate one classifier on one dataset: :func:`benchmark_configs` with a single config and a single dataset.

    The benchmark table (and the narrative-detection table, when the dataset has ``0_0`` documents) is printed and the
    one-row summary is returned, so quick checks and full benchmarks score the same way.

    Works with any classifier that exposes ``classify(text) -> str`` (or ``classify_batch``); only
    :class:`CARDSClassifierBase` subclasses receive context.

    Args:
        classifier: Classifier instance with ``classify`` / ``classify_batch``.
        dataset: A pydantic-evals :class:`Dataset`, e.g. from :func:`nslp_dataset`.
        use_context: When ``False``, ignore every case's ``context`` and classify the claim text alone (the gold
            labels are claim-only annotations, so this is the like-for-like run). Defaults to ``True``: contexts
            are used when present and the classifier supports them.
        category_scores: See :func:`benchmark_configs`.

    Returns:
        The one-row summary DataFrame of :func:`benchmark_configs`.

    Raises:
        RuntimeError: if the classifier raised, so nothing could be scored.
    """
    has_context = any(isinstance(case.inputs, CARDSInput) and case.inputs.context for case in dataset.cases)
    mode: Literal["none", "with"] = (
        "with" if use_context and has_context and isinstance(classifier, CARDSClassifierBase) else "none"
    )
    df = benchmark_configs(
        {type(classifier).__name__: classifier},
        {dataset.name or "dataset": dataset},
        context_modes=(mode,),
        category_scores=category_scores,
    )
    print_benchmark(df)
    error = str(df.iloc[0].get("error", "") or "").strip()
    if error:
        raise RuntimeError(f"evaluation failed: {error}")
    return df


def _f1(metrics: Metrics, depth: int, strategy: str) -> float:
    """The F1 of *strategy* at *depth*, or NaN when nothing was scored."""
    return metrics.prf[depth][strategy][2] if depth in metrics.prf else float("nan")


def benchmark_configs(
    configs: dict[str, Any],
    datasets: dict[str, Dataset],
    context_modes: Sequence[Literal["none", "with"]] = ("none", "with"),
    min_context_coverage: float = 0.5,
    save_dir: str | None = None,
    category_scores: Literal["all", "narrative_only"] = "all",
    config_meta: dict[str, dict[str, Any]] | None = None,
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
        category_scores: Which cases the category scores (exact, hF1, F1, and the saved case rows) cover. ``"all"``
            (default) scores every case, including those whose gold is exactly ``0_0``. ``"narrative_only"`` scores
            only the cases that carry a category, so ``n_cases`` counts those alone. The narrative-detection columns
            (``n_not_climate``, ``rel_*``) are filled in either way whenever a dataset has ``0_0`` cases.
        config_meta: Extra facts per config label saved with the run, currently ``size_b`` / ``active_b`` (model size in
            billions of parameters). They override what is read from the model id (see
            :func:`~climafactskg.classifiers.cards.runs.model_size_from_id`).

    Returns:
        DataFrame with one row per (config, dataset, context mode):

        * identity: ``config``, ``dataset``, ``context``, ``provider``, ``model``, ``prompt``;
        * sizes: ``n_cases`` (every scored case, failures included), ``n_failed`` (predictions that failed and count
          as wrong), ``n_with_context``, ``n_unambiguous`` (cases with a single gold label);
        * scores: ``exact_match``, ``h_f1`` (over all cases), ``exact_answered`` (answered cases only),
          ``d1_*``/``d2_*`` macro and weighted F1 at taxonomy depth 1 and 2, ``macro_f1``/``weighted_f1`` (= depth 2),
          ``micro_f1`` (plain accuracy);
        * context for reading them: ``not_related_rate`` (share of answered predictions saying "not climate"),
          ``exact_unambiguous`` (exact match on single-label gold only), ``baseline_exact`` (best constant label);
        * 95% bootstrap intervals over cases: ``exact_lo/hi``, ``h_f1_lo/hi``, ``d2_macro_f1_lo/hi``;
        * ``error``: the failure text when the whole combination raised (its scores are NaN).

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

    if category_scores not in ("all", "narrative_only"):
        raise ValueError(f"category_scores must be 'all' or 'narrative_only', got {category_scores!r}")
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
                    "n_failed": float("nan"),
                    "exact_answered": float("nan"),
                    "not_related_rate": float("nan"),
                    "exact_unambiguous": float("nan"),
                    "n_unambiguous": float("nan"),
                    "n_detected": float("nan"),
                    "exact_detected": float("nan"),
                    "exact_detected_lo": float("nan"),
                    "exact_detected_hi": float("nan"),
                    "n_category": float("nan"),
                    "exact_category": float("nan"),
                    "n_not_climate": float("nan"),
                    "rel_precision": float("nan"),
                    "rel_recall": float("nan"),
                    "rel_f1": float("nan"),
                    "rel_fpr": float("nan"),
                    "baseline_exact": float("nan"),
                    "exact_lo": float("nan"),
                    "exact_hi": float("nan"),
                    "h_f1_lo": float("nan"),
                    "h_f1_hi": float("nan"),
                    "d2_macro_f1_lo": float("nan"),
                    "d2_macro_f1_hi": float("nan"),
                    "error": str(exc),
                }
            )
            continue

        # Cases without a gold label cannot be scored. A failed prediction (None) is a wrong answer, not a missing one.
        scored = [i for i, case in enumerate(cases) if normalize_gold(case.expected_output)]
        relation = relatedness([preds[i] for i in scored], [cases[i].expected_output for i in scored])
        if category_scores == "narrative_only":
            scored = [i for i in scored if not is_not_climate_gold(cases[i].expected_output)]
        s_preds = [preds[i] for i in scored]
        s_golds = [cases[i].expected_output for i in scored]
        metrics = compute_metrics(s_preds, s_golds)
        per_case = [case_scores(pred, gold) for pred, gold in zip(s_preds, s_golds, strict=True)]
        exact_lo, exact_hi = bootstrap_ci([score[0] for score in per_case])
        hier_lo, hier_hi = bootstrap_ci([score[1] for score in per_case])
        macro_lo, macro_hi = bootstrap_macro_f1(s_preds, s_golds)
        has_negatives = relation.n_not_related > 0
        detected_scores = detected_category_scores(s_preds, s_golds)  # the CARDS category, apart from relatedness
        detected_lo, detected_hi = bootstrap_ci(detected_scores)
        with_category = [
            score[0] for score, gold in zip(per_case, s_golds, strict=True) if not is_not_climate_gold(gold)
        ]

        for i, (pred, gold, (exact, hf1)) in zip(scored, zip(s_preds, s_golds, per_case, strict=True), strict=True):
            case = cases[i]
            case_rows.append(
                {
                    "config": config_name,
                    "dataset": dataset_name,
                    "context": mode,
                    "case_id": case.name,
                    "text": case.inputs.text if isinstance(case.inputs, CARDSInput) else str(case.inputs),
                    "gold": ";".join(normalize_gold(gold)),
                    "pred": "" if pred is None else normalize_label(pred),
                    "exact": exact,
                    "hf1": hf1,
                    "has_context": isinstance(case.inputs, CARDSInput) and bool(case.inputs.context),
                    "gold_d1": project_to_depth(charged_gold(pred, gold, 2), 1),
                    "pred_d1": "" if pred is None else project_to_depth(normalize_label(pred), 1),
                }
            )

        rows.append(
            {
                "config": config_name,
                "dataset": dataset_name,
                "context": mode,
                "n_with_context": sum(1 for c in predict_contexts if c),
                "provider": getattr(classifier, "_provider", "—"),
                "model": getattr(classifier, "_model", type(classifier).__name__),
                "prompt": _prompt_id(classifier),
                "n_cases": metrics.n_cases,
                "n_failed": metrics.n_failed,
                "exact_match": round(metrics.exact, 4),
                "h_f1": round(metrics.hf1, 4),
                "d1_macro_f1": round(_f1(metrics, 1, "macro"), 4),
                "d1_weighted_f1": round(_f1(metrics, 1, "weighted"), 4),
                "d2_macro_f1": round(_f1(metrics, 2, "macro"), 4),
                "d2_weighted_f1": round(_f1(metrics, 2, "weighted"), 4),
                "macro_f1": round(_f1(metrics, 2, "macro"), 4),
                "micro_f1": round(_f1(metrics, 2, "micro"), 4),
                "weighted_f1": round(_f1(metrics, 2, "weighted"), 4),
                "exact_answered": round(metrics.exact_answered, 4),
                "not_related_rate": round(metrics.not_related_rate, 4),
                "exact_unambiguous": round(metrics.exact_unambiguous, 4),
                "n_unambiguous": metrics.n_unambiguous,
                "n_detected": len(detected_scores),
                "exact_detected": round(sum(detected_scores) / len(detected_scores), 4)
                if detected_scores
                else float("nan"),
                "exact_detected_lo": detected_lo,
                "exact_detected_hi": detected_hi,
                "n_category": len(with_category),
                "exact_category": round(sum(with_category) / len(with_category), 4) if with_category else float("nan"),
                "n_not_climate": relation.n_not_related,
                # Only meaningful when the dataset has not-climate documents (load it with climate_only=False).
                "rel_precision": round(relation.precision, 4) if has_negatives else float("nan"),
                "rel_recall": round(relation.recall, 4) if has_negatives else float("nan"),
                "rel_f1": round(relation.f1, 4) if has_negatives else float("nan"),
                "rel_fpr": round(relation.fpr, 4) if has_negatives else float("nan"),
                "baseline_exact": round(metrics.baseline_exact, 4),
                "exact_lo": exact_lo,
                "exact_hi": exact_hi,
                "h_f1_lo": hier_lo,
                "h_f1_hi": hier_hi,
                "d2_macro_f1_lo": macro_lo,
                "d2_macro_f1_hi": macro_hi,
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
            configs_meta = []
            for name, clf in configs.items():
                model = str(getattr(clf, "_model", type(clf).__name__))
                size_b, active_b = model_size_from_id(model)
                entry = {
                    "label": name,
                    "provider": str(getattr(clf, "_provider", "")),
                    "model": model,
                    "prompt": _prompt_id(clf),
                    "size_b": size_b,
                    "active_b": active_b,
                }
                entry.update((config_meta or {}).get(name, {}))
                configs_meta.append(entry)
            run = BenchmarkRun(
                meta=collect_meta(datasets, context_modes, min_context_coverage, configs_meta, category_scores),
                summary=df,
                cases=pd.DataFrame(case_rows, columns=list(CASE_COLUMNS)),
            )
            df.attrs["run_dir"] = str(save_run(run, save_dir))
        except OSError as exc:
            logger.warning("Could not save benchmark run to %s: %s", save_dir, exc)
    return df


# Score columns must never be squeezed (a truncated "0.…" is useless); the text columns give way instead.
_MIN_WIDTHS = {
    "exact_match": 10,
    "h_f1": 10,
    "d1_macro_f1": 6,
    "d2_macro_f1": 6,
    "n_cases": 3,
    "n_failed": 4,
    "n_with_context": 3,
}
# Integer columns: shown without decimals even when another row (a failed combination) has no value for them.
_COUNT_COLUMNS = ("n_cases", "n_failed", "n_with_context", "n_unambiguous")
_COMPACT_COLUMNS = (
    "config",
    "dataset",
    "context",
    "n_cases",
    "n_failed",
    "exact_match",
    "h_f1",
    "d1_macro_f1",
    "d2_macro_f1",
)
# Metric columns that show a dash when nothing was evaluated (n_cases == 0), never a made-up 0.000.
_METRIC_COLUMNS = ("exact_match", "h_f1", "d1_macro_f1", "d1_weighted_f1", "d2_macro_f1", "d2_weighted_f1")


def _shorten_middle(text: str, width: int) -> str:
    """Shortens to *width* keeping both ends, so labels that share a prefix (or a suffix) stay distinguishable."""
    if len(text) <= width:
        return text
    tail = (width - 1) // 2
    return f"{text[: width - 1 - tail]}…{text[len(text) - tail :]}"


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
        ("config", "Config", "bold cyan", "left", 22 if wide else 8, True),
        ("dataset", "Dataset", "", "left", 16 if wide else 10, True),
        ("context", "Ctx", "dim", "left", 4, True),
        ("n_with_context", "Ctx#", "dim", "right", None, False),
        ("provider", "Provider", "dim", "left", 12, True),
        ("model", "Model", "", "left", 22, True),
        ("prompt", "Prompt", "dim italic", "left", 35, True),
        ("n_cases", "N", "", "right", None, False),
        ("n_failed", "Fail", "red", "right", None, False),
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
        for col, _, _, _, mw, _ in present:
            if no_cases and col in _METRIC_COLUMNS:
                cells.append("—")
            elif col in _COUNT_COLUMNS:
                cells.append("—" if pd.isna(row[col]) else str(int(row[col])))
            elif col in ("exact_match", "h_f1"):
                cells.append(_score_cell(row, col))
            elif isinstance(row[col], float):
                cells.append("—" if pd.isna(row[col]) else f"{row[col]:.3f}")
            elif not wide and col in ("config", "dataset"):
                cells.append(_shorten_middle(str(row[col]), cast(int, mw)))
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
    _print_relatedness(df)
    if "context" in df.columns and (df["context"] == "with").any():
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")


def _print_relatedness(df: pd.DataFrame) -> None:
    """A second table with the narrative-detection scores; only printed when a dataset had 0_0 documents."""
    if "rel_f1" not in df.columns or df["rel_f1"].isna().all():
        return
    table = Table(
        title="Narrative detection (denial narrative vs 0_0)", box=box.SIMPLE, collapse_padding=True, pad_edge=False
    )
    for header, justify in (("Config", "left"), ("Dataset", "left"), ("Ctx", "left"), ("0_0 docs", "right")):
        table.add_column(header, justify=cast(Literal["left", "right"], justify), no_wrap=True, max_width=14)
    for header in ("Prec", "Recall", "F1", "False alarm"):
        table.add_column(header, justify="right", no_wrap=True, min_width=6)
    for _, row in df[df["rel_f1"].notna()].iterrows():
        table.add_row(
            str(row["config"]),
            str(row["dataset"]),
            str(row.get("context", "")),
            str(int(row["n_not_climate"])),
            *(
                "—" if pd.isna(row[c]) else f"{row[c]:.3f}"
                for c in ("rel_precision", "rel_recall", "rel_f1", "rel_fpr")
            ),
        )
    _console.print(table)


def _format_p(p: float) -> str:
    """An exact p-value to three decimals, or ``<0.001``."""
    return "—" if pd.isna(p) else ("<0.001" if p < 0.001 else f"{p:.3f}")


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
        ("p", "right", None, 6),
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
            _format_p(row["p_value"]),
        )
    _console.print(table)
    _console.print("[dim]p: exact two-sided McNemar test on the cases that changed.[/dim]")
