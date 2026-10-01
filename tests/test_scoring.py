"""Tests for the shared CARDS scoring: label normalisation, per-case scores and aggregate metrics (offline, pure)."""

import math

import pytest
from climafactskg.classifiers.cards.scoring import (
    bootstrap_macro_f1,
    case_scores,
    charged_gold,
    compute_metrics,
    normalize_gold,
    normalize_label,
)


class TestNormalize:
    def test_not_related_sentinels_are_unified(self):
        assert normalize_label("0") == "0_0"
        assert normalize_label(" 0_0 ") == "0_0"
        assert normalize_label("1_1") == "1_1"

    def test_bare_top_level_codes_become_their_padded_form(self):
        assert normalize_label("1") == "1_0"
        assert normalize_label("5") == "5_0"

    def test_normalize_gold_handles_scalar_list_and_none(self):
        assert normalize_gold("0") == ["0_0"]
        assert normalize_gold(["1_1", "0"]) == ["1_1", "0_0"]
        assert normalize_gold(["1_1", "1_1"]) == ["1_1"]  # duplicates collapse
        assert normalize_gold(None) == []


class TestCaseScores:
    def test_exact_match_against_any_gold_label(self):
        assert case_scores("2_1", ["1_1", "2_1"]) == (1.0, 1.0)

    def test_the_two_not_related_spellings_are_the_same_class(self):
        assert case_scores("0", ["0_0"]) == (1.0, 1.0)
        assert case_scores("0_0", ["0"]) == (1.0, 1.0)

    def test_failed_prediction_scores_zero(self):
        assert case_scores(None, ["1_1"]) == (0.0, 0.0)

    def test_partial_credit_for_the_same_parent_and_zero_for_another_branch(self):
        exact, hf1 = case_scores("2_0", ["2_3"])
        assert exact == 0.0 and hf1 == pytest.approx(2 / 3)
        assert case_scores("1_1", ["2_3"]) == (0.0, 0.0)


class TestComputeMetrics:
    def test_failed_predictions_count_as_wrong_and_are_reported(self):
        m = compute_metrics(["1_1", "1_1", "2_2", None], [["1_1"]] * 4)

        assert (m.n_cases, m.n_failed) == (4, 1)
        assert m.exact == pytest.approx(0.5)  # not 2/3: the failure stays in the denominator
        assert m.exact_answered == pytest.approx(2 / 3)

    def test_micro_f1_is_plain_accuracy(self):
        m = compute_metrics(["1_1", "1_1", "2_2", "2_2"], [["1_1"]] * 4)

        _, _, micro_f1 = m.prf[2]["micro"]
        assert micro_f1 == pytest.approx(0.5) and micro_f1 == pytest.approx(m.exact)

    def test_micro_f1_counts_failures_against_the_model(self):
        m = compute_metrics(["1_1", None], [["1_1"], ["1_1"]])
        assert m.prf[2]["micro"][2] == pytest.approx(0.5)

    def test_macro_f1_is_over_gold_classes_only(self):
        # Documented behaviour: predicted-only classes do not add zero-F1 entries to the macro average.
        m = compute_metrics(["1_1", "1_1", "2_2", "2_2"], [["1_1"]] * 4)
        assert m.prf[2]["macro"][2] == pytest.approx(2 / 3)

    def test_not_related_spellings_are_one_class_in_every_metric(self):
        m = compute_metrics(["0", "0_0"], [["0_0"], ["0_0"]])
        assert m.exact == 1.0 and m.hf1 == 1.0 and m.prf[2]["micro"][2] == 1.0

    def test_not_related_rate_is_over_answered_predictions(self):
        m = compute_metrics(["0", "0_0", "1_1", None], [["1_1"]] * 4)
        assert m.not_related_rate == pytest.approx(2 / 3)

    def test_unambiguous_subset(self):
        m = compute_metrics(["a_0", "b_0", "x_0"], [["a_0"], ["a_0", "b_0"], ["a_0"]])

        assert m.n_unambiguous == 2
        assert m.exact_unambiguous == pytest.approx(0.5)  # right on the first, wrong on the third

    def test_baseline_is_the_best_constant_label(self):
        m = compute_metrics(["a_0"] * 4, [["a_0"], ["a_0", "b_0"], ["b_0"], ["b_0"]])
        assert m.baseline_exact == pytest.approx(0.75)  # always answering b_0 is right on 3 of 4

    def test_both_depths_are_reported_with_all_strategies(self):
        m = compute_metrics(["2_1", "3_2"], [["2_3"], ["3_2"]])

        for depth in (1, 2):
            assert set(m.prf[depth]) == {"macro", "micro", "weighted"}
        assert m.prf[1]["micro"][2] == pytest.approx(1.0)  # both right at depth 1
        assert m.prf[2]["micro"][2] == pytest.approx(0.5)

    def test_empty_input_gives_nan_not_zero(self):
        m = compute_metrics([], [])
        assert m.n_cases == 0 and math.isnan(m.exact) and math.isnan(m.hf1) and m.prf == {}

    def test_length_mismatch_and_empty_gold_are_errors(self):
        with pytest.raises(ValueError):
            compute_metrics(["1_1"], [["1_1"], ["1_1"]])
        with pytest.raises(ValueError):
            compute_metrics(["1_1"], [[]])


class TestBootstrapMacroF1:
    def _data(self):
        preds = ["1_1", "1_1", "2_1", "2_1", "3_1", "3_2"] * 7
        golds = [["1_1"], ["1_1"], ["2_1"], ["2_2"], ["3_1"], ["3_1"]] * 7
        return preds, golds

    def test_is_deterministic_and_ordered(self):
        preds, golds = self._data()
        first = bootstrap_macro_f1(preds, golds)
        assert first == bootstrap_macro_f1(preds, golds)
        assert 0.0 <= first[0] <= first[1] <= 1.0

    def test_perfect_predictions_give_a_degenerate_interval(self):
        golds = [["1_1"], ["2_1"], ["3_1"]] * 5
        assert bootstrap_macro_f1([g[0] for g in golds], golds) == (1.0, 1.0)

    def test_empty_input_gives_nan(self):
        lo, hi = bootstrap_macro_f1([], [])
        assert math.isnan(lo) and math.isnan(hi)


class TestChargedGold:
    def test_a_hit_is_charged_to_the_prediction(self):
        assert charged_gold("2_1", ["3_1", "2_1"]) == "2_1"

    def test_a_miss_is_charged_to_the_closest_gold_label(self):
        assert charged_gold("2_1", ["3_1", "2_3"]) == "2_3"  # shares the 2_0 parent

    def test_a_failure_is_charged_to_the_first_gold_label(self):
        assert charged_gold(None, ["3_1", "2_3"]) == "3_1"

    def test_depth_one_projects_before_charging(self):
        assert charged_gold("2_1", ["3_1", "2_3"], depth=1) == "2_0"
