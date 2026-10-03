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


class TestDepthThreeAndTies:
    def test_depth_three_codes_fold_to_depth_two_everywhere(self):
        assert normalize_label("2_1_1") == "2_1"
        for pred, gold in (("2_1_1", ["2_1"]), ("2_1", ["2_1_1"])):
            m = compute_metrics([pred], [gold])
            assert m.exact == 1.0 and m.hf1 == 1.0 and m.prf[2]["micro"][2] == 1.0  # exact and micro agree

    def test_failure_is_charged_at_depth_one_too(self):
        assert charged_gold(None, ["3_1", "2_3"], depth=1) == "3_0"

    def test_a_perfect_classifier_reaches_macro_one_despite_tie_only_classes(self):
        # 2_1 only ever appears as a second acceptable label, so nobody is charged to it and nobody predicts it.
        m = compute_metrics(["1_1", "0"], [["1_1", "2_1"], ["0_0"]])
        assert m.prf[2]["macro"][2] == pytest.approx(1.0)

    def test_empty_labels_are_not_classes(self):
        assert normalize_gold("") == [] and normalize_gold(["", "1_1"]) == ["1_1"]

    def test_bootstrap_interval_brackets_the_macro_estimate(self):
        preds = ["1_1", "1_1", "2_1", "2_1", "3_1", "3_2", "1_2", "2_2"] * 25
        golds = [["1_1"], ["1_2"], ["2_1"], ["2_2"], ["3_1"], ["3_1"], ["1_2"], ["2_2", "2_1"]] * 25
        point = compute_metrics(preds, golds).prf[2]["macro"][2]
        lo, hi = bootstrap_macro_f1(preds, golds)
        assert lo <= point <= hi


class TestRelatedness:
    def test_confusion_counts_use_the_not_related_spellings_interchangeably(self):
        from climafactskg.classifiers.cards.scoring import relatedness

        golds = [["1_1"], ["1_1"], ["0_0"], ["0_0"]]
        r = relatedness(["1_1", "0_0", "0", "2_2"], golds)  # hit, miss, correct reject, false alarm

        assert (r.n_related, r.n_not_related) == (2, 2)
        assert (r.precision, r.recall, r.f1, r.fpr) == (0.5, 0.5, 0.5, 0.5)

    def test_only_relatedness_counts_not_the_category(self):
        from climafactskg.classifiers.cards.scoring import relatedness

        r = relatedness(["2_2"], [["1_1"]])  # wrong category, but still "related"

        assert r.recall == 1.0

    def test_a_failed_prediction_is_wrong_on_either_side(self):
        from climafactskg.classifiers.cards.scoring import relatedness

        r = relatedness([None, None], [["1_1"], ["0_0"]])

        assert r.recall == 0.0 and r.fpr == 1.0

    def test_tied_gold_sets_that_include_not_related_are_left_out(self):
        from climafactskg.classifiers.cards.scoring import relatedness

        r = relatedness(["1_1", "1_1"], [["0_0", "1_1"], ["1_1"]])

        assert (r.n_related, r.n_not_related) == (1, 0)

    def test_undefined_rates_are_nan_not_zero(self):
        import math

        from climafactskg.classifiers.cards.scoring import relatedness

        r = relatedness(["1_1"], [["1_1"]])  # no negatives: no false-positive rate, precision is trivially 1

        assert math.isnan(r.fpr) and r.recall == 1.0

    def test_pure_not_climate_gold_is_detected(self):
        from climafactskg.classifiers.cards.scoring import is_not_climate_gold

        assert is_not_climate_gold(["0"]) and is_not_climate_gold(["0_0"])
        assert not is_not_climate_gold(["0_0", "1_1"]) and not is_not_climate_gold(["1_1"])


class TestCategoryWhenDetected:
    """The CARDS category score, separated from relatedness: only cases where a narrative exists and was detected."""

    def _scores(self, preds, golds):
        from climafactskg.classifiers.cards.scoring import detected_category_scores

        return detected_category_scores(preds, golds)

    def test_only_cases_with_a_category_that_the_model_detected_are_scored(self):
        golds = [["1_1"], ["1_1"], ["1_1"], ["0_0"], ["0_0", "2_1"]]
        preds = ["1_1", "2_2", "0", "1_1", "2_1"]

        # hit, wrong category, narrative missed (excluded), no category in the gold (excluded), tie resolved
        assert self._scores(preds, golds) == [1.0, 0.0, 1.0]

    def test_a_failed_prediction_is_not_a_detection(self):
        assert self._scores([None], [["1_1"]]) == []

    def test_a_tied_gold_that_accepts_not_related_does_not_count_a_not_related_answer(self):
        assert self._scores(["0_0"], [["0_0", "1_1"]]) == []

    def test_labels_are_compared_at_depth_two(self):
        assert self._scores(["2_1_1"], [["2_1"]]) == [1.0]

    def test_nothing_detected_gives_an_empty_list(self):
        assert self._scores(["0", "0_0"], [["1_1"], ["2_1"]]) == []
