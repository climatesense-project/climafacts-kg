"""Pydantic-evals evaluators for CARDS taxonomy classification.

Per-case evaluators
-------------------
CARDSOneOfMatch
    Exact match: score is 1.0 if the prediction appears in the gold label set,
    0.0 otherwise.  Matches :func:`benchmark_configs` hit/miss semantics.

CARDSHierarchicalMatch
    Partial-credit hF1: 1.0 for exact match, a partial score for same-branch
    misses, 0.0 for a completely wrong branch.

Aggregate scores live in :mod:`.scoring` and are reported by :func:`.eval.benchmark_configs`.

Taxonomy utilities
------------------
project_to_depth
    Fold a label to a coarser depth, padded to exactly two parts.

ancestors_of
    Return the structural ancestor set of a hierarchical label.
"""

import logging
from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

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
