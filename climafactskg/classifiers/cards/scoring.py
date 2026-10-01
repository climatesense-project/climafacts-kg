"""Shared CARDS scoring: label normalisation, per-case scores and aggregate metrics.

One implementation used by ``evaluate`` (console tables) and ``benchmark_configs`` (summary rows), so the numbers cannot
drift apart. Pure functions, no pydantic-evals dependency.

Conventions
-----------
* A prediction of ``None`` (the LLM engine's "still failed after retries") is a **wrong answer**: it stays in every
  denominator, and ``n_failed`` reports how many there were.
* ``"0"`` and ``"0_0"`` are the same class ("not climate misinformation"); both spellings are normalised to ``"0_0"``.
* Hit/miss is "the prediction is any acceptable gold label". For the F1 family a miss is *charged* to the hierarchically
  closest gold label (a hit is charged to the prediction), giving exactly one false negative per miss.
* Micro-F1 is computed over every label that occurs, so it equals plain accuracy (failures included). Macro and weighted
  F1 average over the classes that occur in some gold set, so predicted-only classes do not add zero-F1 entries.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

FAILED = "__failed__"
_STRATEGIES = ("macro", "micro", "weighted")

# The classifier only produces codes with at most two ``_``-separated parts (e.g. ``"2_3"``). Depth-3 gold labels from
# annotations are projected down to this depth before comparison.
_MAX_CLASSIFIER_DEPTH = 2


def project_to_depth(label: str, depth: int) -> str:
    """Project a label to a coarser depth, padded to ``_MAX_CLASSIFIER_DEPTH`` parts.

    All projected labels have exactly :data:`_MAX_CLASSIFIER_DEPTH` (2) underscore-separated parts, so labels from
    different original depths compare as plain strings. Depth-3 gold labels (e.g. ``"5_3_1"``) are folded into the
    depth-2 space understood by the classifier.

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

    Ancestors are derived structurally: each prefix of the ``_``-separated parts is padded with ``"0"`` to form the
    canonical node at that depth. Works for any number of levels without a taxonomy lookup.

    Single-segment codes (e.g. ``"1"``) are normalised to their ``"_0"`` equivalent (``"1_0"``) before processing so
    that bare top-level codes participate in the hierarchy on the same footing as the padded parent-fallback codes
    returned by :class:`CARDSLLMClassifier`.

    Examples::

        ancestors_of("2_3")   == frozenset({"2_0", "2_3"})
        ancestors_of("1_2_3") == frozenset({"1_0_0", "1_2_0", "1_2_3"})
        ancestors_of("1_0")   == frozenset({"1_0"})
        ancestors_of("0_0")   == frozenset({"0_0"})
        ancestors_of("1")     == frozenset({"1_0"})
        ancestors_of("0")     == frozenset({"0_0"})
    """
    parts = label.split("_")
    # Bare single-segment codes ("1", "0", …) are treated as their "_0" fallback so they connect to the rest of the
    # hierarchy in hF1 comparisons.
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


def normalize_label(label: Any) -> str:
    """Strips a label and pads a bare top-level code to its ``X_0`` form (so ``"0"`` and ``"0_0"`` are one class)."""
    text = str(label).strip()
    return f"{text}_0" if text.isdigit() else text


def normalize_gold(expected: Any) -> list[str]:
    """Normalises a gold specification (``None``, one label, or several) to a de-duplicated list of labels."""
    if expected is None:
        return []
    items = [expected] if isinstance(expected, (str, bytes)) or not isinstance(expected, Iterable) else list(expected)
    return list(dict.fromkeys(normalize_label(item) for item in items))


def case_scores(pred: str | None, golds: Any) -> tuple[float, float]:
    """``(exact, hF1)`` of one prediction against its gold labels. A ``None`` prediction scores ``(0, 0)``."""
    gold = normalize_gold(golds)
    if pred is None:
        return (0.0, 0.0)
    label = normalize_label(pred)
    if label in gold:
        return (1.0, 1.0)
    a_pred = ancestors_of(label)
    return (0.0, max((_hierarchical_f1(a_pred, ancestors_of(g)) for g in gold), default=0.0))


@dataclass(frozen=True)
class Metrics:
    """Aggregate metrics over a set of scored cases. ``prf[depth][strategy] = (precision, recall, f1)``."""

    n_cases: int
    n_failed: int
    exact: float
    hf1: float
    exact_answered: float
    hf1_answered: float
    not_related_rate: float
    exact_unambiguous: float
    n_unambiguous: int
    baseline_exact: float
    prf: dict[int, dict[str, tuple[float, float, float]]] = field(default_factory=dict)


def _charged_label(pred: str, golds: list[str]) -> str:
    """A hit is charged to the prediction; a miss (or a failure) to the hierarchically closest gold label."""
    if pred == FAILED:
        return golds[0]
    if pred in golds:
        return pred
    a_pred = ancestors_of(pred)
    return max(golds, key=lambda gold: _hierarchical_f1(a_pred, ancestors_of(gold)))


def _charged_arrays(
    preds: Sequence[str | None], golds: Sequence[list[str]], depth: int
) -> tuple[list[str], list[str], set[str]]:
    """``(y_true, y_pred, gold_labels)`` at *depth* for already-normalised predictions and gold lists."""
    y_true: list[str] = []
    y_pred: list[str] = []
    gold_labels: set[str] = set()
    for pred, gold in zip(preds, golds, strict=True):
        gold_d = list(dict.fromkeys(project_to_depth(label, depth) for label in gold))
        pred_d = FAILED if pred is None else project_to_depth(pred, depth)
        y_pred.append(pred_d)
        y_true.append(_charged_label(pred_d, gold_d))
        gold_labels.update(gold_d)
    return y_true, y_pred, gold_labels


def _prepare(preds: Sequence[str | None], golds: Sequence[Any]) -> tuple[list[str | None], list[list[str]]]:
    if len(preds) != len(golds):
        raise ValueError(f"{len(preds)} predictions but {len(golds)} gold sets")
    norm_golds = [normalize_gold(gold) for gold in golds]
    if any(not gold for gold in norm_golds):
        raise ValueError("every case needs at least one gold label; filter cases without gold before scoring")
    return [None if pred is None else normalize_label(pred) for pred in preds], norm_golds


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else float("nan")


def compute_metrics(preds: Sequence[str | None], golds: Sequence[Any]) -> Metrics:
    """Scores predictions against gold label sets (see the module docstring for the conventions).

    Raises:
        ValueError: if the lengths differ or a case has no gold label.
    """
    norm_preds, norm_golds = _prepare(preds, golds)
    n = len(norm_preds)
    if n == 0:
        nan = float("nan")
        return Metrics(0, 0, nan, nan, nan, nan, nan, nan, 0, nan, {})

    scores = [case_scores(pred, gold) for pred, gold in zip(norm_preds, norm_golds, strict=True)]
    exact = [s[0] for s in scores]
    hf1 = [s[1] for s in scores]
    answered = [i for i, pred in enumerate(norm_preds) if pred is not None]
    unambiguous = [i for i, gold in enumerate(norm_golds) if len(gold) == 1]
    candidates = {label for gold in norm_golds for label in gold}

    prf: dict[int, dict[str, tuple[float, float, float]]] = {}
    for depth in range(1, _MAX_CLASSIFIER_DEPTH + 1):
        y_true, y_pred, gold_labels = _charged_arrays(norm_preds, norm_golds, depth)
        prf[depth] = {}
        for strategy in _STRATEGIES:
            labels = sorted(set(y_true) | set(y_pred)) if strategy == "micro" else sorted(gold_labels)
            p, r, f1, _ = precision_recall_fscore_support(
                y_true,
                y_pred,
                average=cast(Literal["binary", "micro", "macro", "samples", "weighted"], strategy),
                labels=labels,
                zero_division=0,
            )
            prf[depth][strategy] = (float(p), float(r), float(f1))

    return Metrics(
        n_cases=n,
        n_failed=n - len(answered),
        exact=_mean(exact),
        hf1=_mean(hf1),
        exact_answered=_mean([exact[i] for i in answered]),
        hf1_answered=_mean([hf1[i] for i in answered]),
        not_related_rate=_mean([1.0 if norm_preds[i] == "0_0" else 0.0 for i in answered]),
        exact_unambiguous=_mean([exact[i] for i in unambiguous]),
        n_unambiguous=len(unambiguous),
        baseline_exact=max(sum(label in gold for gold in norm_golds) / n for label in candidates),
        prf=prf,
    )


def bootstrap_macro_f1(
    preds: Sequence[str | None],
    golds: Sequence[Any],
    depth: int = _MAX_CLASSIFIER_DEPTH,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """Deterministic percentile bootstrap interval (over cases) of the macro F1 at *depth*.

    Uses the same charging and class set as :func:`compute_metrics` (classes that occur in some gold set; a class that
    is absent from a resample scores F1 = 0, as scikit-learn's ``zero_division=0`` does).
    """
    norm_preds, norm_golds = _prepare(preds, golds)
    if not norm_preds:
        return (float("nan"), float("nan"))
    y_true, y_pred, gold_labels = _charged_arrays(norm_preds, norm_golds, depth)
    labels = sorted(gold_labels)
    index = {label: i for i, label in enumerate(labels)}
    k = len(labels)
    true_idx = np.array([index[label] for label in y_true])
    pred_idx = np.array([index.get(label, k) for label in y_pred])  # predicted-only classes map to the extra slot k

    rng = np.random.default_rng(seed)
    resamples = rng.integers(0, len(true_idx), size=(n_boot, len(true_idx)))
    scores = np.empty(n_boot)
    for b, rows in enumerate(resamples):
        t, p = true_idx[rows], pred_idx[rows]
        hit = t == p
        tp = np.bincount(t[hit], minlength=k + 1)[:k]
        fp = np.bincount(p[~hit], minlength=k + 1)[:k]
        fn = np.bincount(t[~hit], minlength=k + 1)[:k]
        denominator = 2 * tp + fp + fn
        scores[b] = float(np.mean(np.divide(2 * tp, denominator, out=np.zeros(k), where=denominator > 0)))
    lo, hi = np.percentile(scores, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return (float(lo), float(hi))


__all__ = [
    "FAILED",
    "Metrics",
    "ancestors_of",
    "bootstrap_macro_f1",
    "case_scores",
    "compute_metrics",
    "normalize_gold",
    "normalize_label",
    "project_to_depth",
]
