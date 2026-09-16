"""Tests for the pure hierarchical-label helpers and per-case evaluators.

Covers climafactskg.classifiers.cards.evaluators.
"""

from types import SimpleNamespace

import pytest
from climafactskg.classifiers.cards.evaluators import (
    CARDSHierarchicalMatch,
    CARDSOneOfMatch,
    ancestors_of,
    project_to_depth,
)


class TestProjectToDepth:
    def test_depth3_to_depth1(self):
        assert project_to_depth("5_3_1", 1) == "5_0"

    def test_depth2_to_depth1(self):
        assert project_to_depth("5_3", 1) == "5_0"

    def test_depth2_stays_depth2(self):
        assert project_to_depth("1_0", 1) == "1_0"

    def test_depth3_to_depth2(self):
        assert project_to_depth("5_3_1", 2) == "5_3"

    def test_depth2_to_depth2_noop(self):
        assert project_to_depth("5_3", 2) == "5_3"

    def test_bare_top_level_to_depth1(self):
        assert project_to_depth("1", 1) == "1_0"

    def test_result_always_has_two_parts(self):
        for label, depth in [("5_3_1", 1), ("5_3_1", 2), ("1", 1), ("0", 2)]:
            assert len(project_to_depth(label, depth).split("_")) == 2


class TestAncestorsOf:
    def test_depth2_label(self):
        assert ancestors_of("2_3") == frozenset({"2_0", "2_3"})

    def test_depth3_label(self):
        assert ancestors_of("1_2_3") == frozenset({"1_0_0", "1_2_0", "1_2_3"})

    def test_already_padded_depth2(self):
        assert ancestors_of("1_0") == frozenset({"1_0"})

    def test_zero_zero(self):
        assert ancestors_of("0_0") == frozenset({"0_0"})

    def test_bare_top_level(self):
        assert ancestors_of("1") == frozenset({"1_0"})

    def test_bare_zero(self):
        assert ancestors_of("0") == frozenset({"0_0"})

    def test_label_always_a_member_of_its_own_ancestors(self):
        for label in ["2_3", "1_2_3", "1_0", "0_0", "5"]:
            padded = label if "_" in label else f"{label}_0"
            assert padded in ancestors_of(label)


class TestCARDSOneOfMatch:
    def setup_method(self):
        self.evaluator = CARDSOneOfMatch()

    def test_exact_match_scores_one(self):
        ctx = SimpleNamespace(output="2_3", expected_output=["2_3"])
        assert self.evaluator.evaluate(ctx) == 1.0

    def test_match_against_any_of_multiple_gold_labels(self):
        ctx = SimpleNamespace(output="2_3", expected_output=["1_1", "2_3", "5_0"])
        assert self.evaluator.evaluate(ctx) == 1.0

    def test_mismatch_scores_zero(self):
        ctx = SimpleNamespace(output="1_1", expected_output=["2_3"])
        assert self.evaluator.evaluate(ctx) == 0.0


class TestCARDSHierarchicalMatch:
    def setup_method(self):
        self.evaluator = CARDSHierarchicalMatch()

    def test_exact_match_scores_one(self):
        ctx = SimpleNamespace(output="2_3", expected_output=["2_3"])
        assert self.evaluator.evaluate(ctx) == 1.0

    def test_same_branch_partial_credit(self):
        # "2_1" vs "2_3": share parent "2_0" but not the leaf -> partial score in (0, 1).
        ctx = SimpleNamespace(output="2_1", expected_output=["2_3"])
        score = self.evaluator.evaluate(ctx)
        assert 0.0 < score < 1.0

    def test_wrong_branch_scores_zero(self):
        ctx = SimpleNamespace(output="1_1", expected_output=["2_3"])
        assert self.evaluator.evaluate(ctx) == 0.0

    def test_best_of_multiple_expected_labels(self):
        # Prediction matches "2_3" exactly, even though "1_1" is also a valid gold label.
        ctx = SimpleNamespace(output="2_3", expected_output=["1_1", "2_3"])
        assert self.evaluator.evaluate(ctx) == 1.0

    def test_scalar_expected_output_is_wrapped(self):
        ctx = SimpleNamespace(output="2_3", expected_output="2_3")
        assert self.evaluator.evaluate(ctx) == 1.0


@pytest.mark.parametrize(
    ("pred", "expected", "score"),
    [
        ("0_0", ["0_0"], 1.0),
        ("0", ["0_0"], 1.0),
    ],
)
def test_hierarchical_match_handles_fallback_codes(pred, expected, score):
    ctx = SimpleNamespace(output=pred, expected_output=expected)
    assert CARDSHierarchicalMatch().evaluate(ctx) == score
