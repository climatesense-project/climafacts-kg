"""Pydantic-evals evaluators for CARDS taxonomy classification.

Per-case evaluators
-------------------
CARDSOneOfMatch
    Exact match: score is 1.0 if the prediction appears in the gold label set,
    0.0 otherwise.  Matches :func:`benchmark_configs` hit/miss semantics.

CARDSHierarchicalMatch
    Partial-credit hF1: 1.0 for exact match, a partial score for same-branch
    misses, 0.0 for a completely wrong branch.

Aggregate report evaluators
----------------------------
MultiMetricsReportEvaluator
    Macro / micro / weighted precision, recall, and F1 via scikit-learn.

HierarchicalMetricsReportEvaluator
    Mean exact-match rate and mean hF1 across all cases.

DepthMetricsReportEvaluator
    Macro / micro / weighted F1 after projecting labels to each taxonomy depth.

Taxonomy utilities
------------------
project_to_depth
    Fold a label to a coarser depth, padded to exactly two parts.

ancestors_of
    Return the structural ancestor set of a hierarchical label.
"""

import logging
from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    ReportEvaluator,
    ReportEvaluatorContext,
)
from pydantic_evals.reporting import TableResult

# Shared scoring lives in :mod:`.scoring`; these names stay importable from here.
from .scoring import (  # noqa: F401
    _MAX_CLASSIFIER_DEPTH,
    _hierarchical_f1,
    ancestors_of,
    case_scores,
    compute_metrics,
    project_to_depth,
)

logger = logging.getLogger(__name__)


@dataclass
class CARDSOneOfMatch(Evaluator):
    """Exact-match evaluator: 1.0 if the prediction appears in the gold set, 0.0 otherwise.

    The gold set is a list of equally-valid labels (annotator disagreement or
    multi-label ground truth).  A prediction is correct if it matches *any* of them.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return case_scores(ctx.output, ctx.expected_output)[0]


@dataclass
class CARDSHierarchicalMatch(Evaluator):
    """Partial-credit evaluator based on hierarchical label proximity.

    Returns 1.0 for an exact match (consistent with :class:`CARDSOneOfMatch`),
    a partial score for same-branch misses, and 0.0 for a completely wrong branch.

    The score is the hierarchical F1 (hF1) between the predicted label's ancestor
    set and the ancestor set of the *best-matching* expected label — i.e. the
    expected label whose ancestors overlap most with the prediction.  This is
    consistent with :class:`CARDSOneOfMatch` semantics: the model is only required
    to predict one valid label, so it is judged against the closest valid answer.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return case_scores(ctx.output, ctx.expected_output)[1]


def _predictions_and_gold(ctx: ReportEvaluatorContext[Any, Any, Any]) -> tuple[list[str | None], list[Any]]:
    """Predictions (``None`` for a failed item) and gold sets of every case that has a gold label."""
    preds: list[str | None] = []
    golds: list[Any] = []
    for case in ctx.report.cases:
        if case.expected_output is None:
            continue
        preds.append(None if case.output is None else str(case.output))
        golds.append(case.expected_output)
    return preds, golds


class HierarchicalMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports mean exact-match and mean hF1 across all evaluated cases.

    Computed by :func:`.scoring.compute_metrics`: a failed prediction (``None``) counts as wrong and stays in the
    denominator; when any failed, the table also states how many and the score over the answered cases only.
    """

    def __init__(self, name: str = "hierarchical_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        preds, golds = _predictions_and_gold(ctx)
        m = compute_metrics(preds, golds)
        logger.info("Hierarchical match (mean hF1): %.4f", m.hf1)
        logger.info("Exact match (CARDSOneOfMatch): %.4f", m.exact)

        scored = m.n_cases > 0
        rows = [
            ["Exact match (CARDSOneOfMatch)", f"{m.exact:.4f}" if scored else "—"],
            ["Hierarchical match (hF1)", f"{m.hf1:.4f}" if scored else "—"],
        ]
        if m.n_failed:
            rows += [
                ["Failed predictions (counted as wrong)", f"{m.n_failed} of {m.n_cases}"],
                ["Exact match (answered only)", f"{m.exact_answered:.4f}"],
            ]
        return TableResult(title="Hierarchical Match Report", columns=["Metric", "Score"], rows=rows)


class MultiMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports macro / micro / weighted precision, recall, and F1 at depth 2 via :func:`.scoring.compute_metrics`.

    The expected output per case is an unordered set of equally-valid labels (annotator disagreement). A hit is charged
    to the prediction and a miss to the hierarchically closest gold label (one false negative per miss). Micro is
    plain accuracy over every label that occurs (failures included); macro and weighted average over the classes that
    occur in some gold set, so predicted-only classes do not dilute the average with spurious F1 = 0 entries.
    """

    def __init__(self, name: str = "multi_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        preds, golds = _predictions_and_gold(ctx)
        if not preds:
            return TableResult(title="Metrics Summary", columns=["Metric", "Value"], rows=[])
        metrics = compute_metrics(preds, golds)
        rows = []
        for strategy in ("macro", "micro", "weighted"):
            p, r, f1 = metrics.prf[_MAX_CLASSIFIER_DEPTH][strategy]
            rows.append([strategy.capitalize(), f"{p:.4f}", f"{r:.4f}", f"{f1:.4f}"])
        return TableResult(
            title="Performance Report",
            columns=["Weighting Method", "Precision", "Recall", "F1 Score"],
            rows=rows,
        )


class DepthMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports macro / micro / weighted precision, recall and F1 at each classifier taxonomy depth (1 and 2).

    Complements :class:`MultiMetricsReportEvaluator` with a depth breakdown: for each depth, predicted and gold labels
    are projected via :func:`project_to_depth` and hit/miss is re-determined at the projected level. Depth-3 gold
    labels are folded into depth-2 space so evaluation stays within the classifier's output range.
    """

    def __init__(self, name: str = "depth_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        preds, golds = _predictions_and_gold(ctx)
        metrics = compute_metrics(preds, golds)
        rows = []
        for depth in range(1, _MAX_CLASSIFIER_DEPTH + 1):
            for strategy in ("macro", "micro", "weighted"):
                if depth in metrics.prf:
                    p, r, f1 = metrics.prf[depth][strategy]
                    rows.append([f"Depth {depth}", strategy.capitalize(), f"{p:.4f}", f"{r:.4f}", f"{f1:.4f}"])
                else:
                    rows.append([f"Depth {depth}", strategy.capitalize(), "—", "—", "—"])
        return TableResult(
            title="Performance Report by Taxonomy Depth",
            columns=["Depth", "Weighting", "Precision", "Recall", "F1 Score"],
            rows=rows,
        )
