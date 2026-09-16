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
from typing import Any, Iterable, Literal, cast

from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    ReportEvaluator,
    ReportEvaluatorContext,
)
from pydantic_evals.reporting import TableResult
from sklearn.metrics import precision_recall_fscore_support

logger = logging.getLogger(__name__)

# The classifier only produces codes with at most two ``_``-separated parts
# (e.g. ``"2_3"``).  Depth-3 gold labels from annotations are projected down
# to this depth before comparison.
_MAX_CLASSIFIER_DEPTH = 2


def project_to_depth(label: str, depth: int) -> str:
    """Project a label to a coarser depth, padded to ``_MAX_CLASSIFIER_DEPTH`` parts.

    All projected labels have exactly :data:`_MAX_CLASSIFIER_DEPTH` (2)
    underscore-separated parts, so labels from different original depths compare
    as plain strings.  Depth-3 gold labels (e.g. ``"5_3_1"``) are folded into
    the depth-2 space understood by the classifier.

    Examples::

        project_to_depth("5_3_1", 1) == "5_0"
        project_to_depth("5_3",   1) == "5_0"
        project_to_depth("1_0",   1) == "1_0"
        project_to_depth("5_3_1", 2) == "5_3"
        project_to_depth("5_3",   2) == "5_3"
        project_to_depth("1",     1) == "1_0"
    """
    parts = label.split("_")
    if len(parts) == 1:
        parts = [parts[0], "0"]
    return "_".join(parts[:depth] + ["0"] * (_MAX_CLASSIFIER_DEPTH - depth))


def ancestors_of(label: str) -> frozenset[str]:
    """Return the ancestor set of a hierarchical label, including the label itself.

    Ancestors are derived structurally: each prefix of the ``_``-separated parts
    is padded with ``"0"`` to form the canonical node at that depth.  Works for
    any number of levels without a taxonomy lookup.

    Single-segment codes (e.g. ``"1"``) are normalised to their ``"_0"``
    equivalent (``"1_0"``) before processing so that bare top-level codes
    participate in the hierarchy on the same footing as the padded parent-
    fallback codes returned by :class:`CARDSLLMClassifier`.

    Examples::

        ancestors_of("2_3")   == frozenset({"2_0", "2_3"})
        ancestors_of("1_2_3") == frozenset({"1_0_0", "1_2_0", "1_2_3"})
        ancestors_of("1_0")   == frozenset({"1_0"})
        ancestors_of("0_0")   == frozenset({"0_0"})
        ancestors_of("1")     == frozenset({"1_0"})
        ancestors_of("0")     == frozenset({"0_0"})
    """
    parts = label.split("_")
    # Bare single-segment codes ("1", "0", …) are treated as their "_0" fallback
    # so they connect to the rest of the hierarchy in hF1 comparisons.
    if len(parts) == 1:
        parts = [parts[0], "0"]
    nodes: set[str] = set()
    for depth in range(len(parts)):
        node_parts = parts[: depth + 1] + ["0"] * (len(parts) - depth - 1)
        nodes.add("_".join(node_parts))
    return frozenset(nodes)


def _hierarchical_f1(a_pred: frozenset[str], a_true: frozenset[str]) -> float:
    """Compute hF1 between two ancestor sets."""
    intersection = len(a_pred & a_true)
    if intersection == 0:
        return 0.0
    hp = intersection / len(a_pred)
    hr = intersection / len(a_true)
    return 2 * hp * hr / (hp + hr)


@dataclass
class CARDSOneOfMatch(Evaluator):
    """Exact-match evaluator: 1.0 if the prediction appears in the gold set, 0.0 otherwise.

    The gold set is a list of equally-valid labels (annotator disagreement or
    multi-label ground truth).  A prediction is correct if it matches *any* of them.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return 1.0 if ctx.output in ctx.expected_output else 0.0


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
        pred = str(ctx.output)
        expected = ctx.expected_output
        if isinstance(expected, str) or not isinstance(expected, Iterable):
            expected = [str(expected)]
        else:
            expected = [str(e) for e in expected]

        if pred in expected:
            return 1.0

        a_pred = ancestors_of(pred)
        return max(_hierarchical_f1(a_pred, ancestors_of(e)) for e in expected)


class HierarchicalMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports mean exact-match and mean hF1 across all evaluated cases.

    Reads the pre-computed :class:`CARDSOneOfMatch` and
    :class:`CARDSHierarchicalMatch` scores from each case result, averages them,
    and returns a two-row summary table.
    """

    def __init__(self, name: str = "hierarchical_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        hier_scores: list[float] = []
        exact_scores: list[float] = []
        for case in ctx.report.cases:
            if case.output is None:
                continue
            if (h := case.scores.get("CARDSHierarchicalMatch")) is not None:
                hier_scores.append(h.value)
            if (e := case.scores.get("CARDSOneOfMatch")) is not None:
                exact_scores.append(e.value)

        mean_hier = sum(hier_scores) / len(hier_scores) if hier_scores else 0.0
        mean_exact = sum(exact_scores) / len(exact_scores) if exact_scores else 0.0
        logger.info("Hierarchical match (mean hF1): %.4f", mean_hier)
        logger.info("Exact match (CARDSOneOfMatch): %.4f", mean_exact)

        return TableResult(
            title="Hierarchical Match Report",
            columns=["Metric", "Score"],
            rows=[
                ["Exact match (CARDSOneOfMatch)", f"{mean_exact:.4f}"],
                ["Hierarchical match (hF1)", f"{mean_hier:.4f}"],
            ],
        )


class MultiMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports macro / micro / weighted precision, recall, and F1 via scikit-learn.

    The expected output per case is an unordered set of equally-valid labels
    (annotator disagreement).  Hit/miss is read from the pre-computed
    :class:`CARDSOneOfMatch` score:

    * **Hit** (score == 1.0): ``y_true = predicted`` → TP for predicted class.
    * **Miss** (score == 0.0): ``y_true = hierarchically closest expected label``
      → FP for predicted class + FN for one gold class.  Exactly one FN per
      miss keeps per-class recall comparable regardless of how many valid labels
      a claim has.

    Only classes that appear in at least one gold set are passed as ``labels``
    to scikit-learn so that predicted-only classes (never a gold label) do not
    dilute the macro average with spurious F1 = 0 entries.
    """

    def __init__(self, name: str = "multi_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        y_true: list[str] = []
        y_pred: list[str] = []
        true_classes: set[str] = set()

        for case in ctx.report.cases:
            if case.output is None or case.expected_output is None:
                continue

            predicted = str(case.output)
            expected = case.expected_output
            if isinstance(expected, (str, bytes)) or not isinstance(expected, Iterable):
                expected_labels = [str(expected)]
            else:
                expected_labels = [str(e) for e in expected] or [str(expected)]

            true_classes.update(expected_labels)

            one_of = case.scores.get("CARDSOneOfMatch")
            if one_of is not None and one_of.value == 1.0:
                y_true.append(predicted)
            else:
                a_pred = ancestors_of(predicted)
                charged = max(
                    expected_labels,
                    key=lambda e: _hierarchical_f1(a_pred, ancestors_of(e)),
                )
                y_true.append(charged)

            y_pred.append(predicted)

        if not y_true:
            return TableResult(title="Metrics Summary", columns=["Metric", "Value"], rows=[])

        gold_labels = sorted(true_classes)
        rows = []
        for strategy in ("macro", "micro", "weighted"):
            p, r, f1, _ = precision_recall_fscore_support(
                y_true,
                y_pred,
                average=cast(Literal["binary", "micro", "macro", "samples", "weighted"], strategy),
                labels=gold_labels,
                zero_division=0,
            )
            rows.append([strategy.capitalize(), f"{p:.4f}", f"{r:.4f}", f"{f1:.4f}"])

        return TableResult(
            title="Performance Report",
            columns=["Weighting Method", "Precision", "Recall", "F1 Score"],
            rows=rows,
        )


class DepthMetricsReportEvaluator(ReportEvaluator[Any, Any, Any]):
    """Reports macro / micro / weighted F1 at each classifier taxonomy depth (1 and 2).

    Complements :class:`MultiMetricsReportEvaluator` with a depth breakdown.  For
    each depth *d*, predicted and gold labels are projected via
    :func:`project_to_depth` and hit/miss is re-determined at the projected level.
    Depth-3 gold labels are folded into depth-2 space so evaluation stays within
    the classifier's output range.
    """

    def __init__(self, name: str = "depth_metrics_report"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, ctx: ReportEvaluatorContext[Any, Any, Any]) -> TableResult:
        rows = []
        for depth in range(1, _MAX_CLASSIFIER_DEPTH + 1):
            y_true: list[str] = []
            y_pred: list[str] = []
            true_classes: set[str] = set()

            for case in ctx.report.cases:
                if case.output is None or case.expected_output is None:
                    continue

                predicted_proj = project_to_depth(str(case.output), depth)
                expected = case.expected_output
                if isinstance(expected, (str, bytes)) or not isinstance(expected, Iterable):
                    expected_labels = [str(expected)]
                else:
                    expected_labels = [str(e) for e in expected] or [str(expected)]

                gold_proj = [project_to_depth(e, depth) for e in expected_labels]
                true_classes.update(gold_proj)

                if predicted_proj in gold_proj:
                    y_true.append(predicted_proj)
                else:
                    a_pred = ancestors_of(predicted_proj)
                    charged = max(gold_proj, key=lambda g: _hierarchical_f1(a_pred, ancestors_of(g)))
                    y_true.append(charged)

                y_pred.append(predicted_proj)

            if not y_true:
                for strategy in ("Macro", "Micro", "Weighted"):
                    rows.append([f"Depth {depth}", strategy, "—", "—", "—"])
                continue

            gold_labels = sorted(true_classes)
            for strategy in ("macro", "micro", "weighted"):
                p, r, f1, _ = precision_recall_fscore_support(
                    y_true,
                    y_pred,
                    average=cast(Literal["binary", "micro", "macro", "samples", "weighted"], strategy),
                    labels=gold_labels,
                    zero_division=0,
                )
                rows.append([f"Depth {depth}", strategy.capitalize(), f"{p:.4f}", f"{r:.4f}", f"{f1:.4f}"])

        return TableResult(
            title="Performance Report by Taxonomy Depth",
            columns=["Depth", "Weighting", "Precision", "Recall", "F1 Score"],
            rows=rows,
        )
