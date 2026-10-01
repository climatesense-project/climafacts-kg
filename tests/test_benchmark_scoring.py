"""benchmark_configs scoring: failures, the not-related spellings, micro-F1, and the extra reliability columns."""

import numpy as np
from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import CARDSInput, benchmark_configs
from climafactskg.classifiers.cards.evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch
from climafactskg.classifiers.cards.runs import load_run
from pydantic_evals import Case, Dataset


class _Fixed(CARDSClassifierBase):
    """Answers the i-th claim with preds[i] (``None`` simulates an item that failed after retries)."""

    def __init__(self, preds):
        self.preds = preds

    def classify(self, text, context=None):
        return self.preds[int(text.split()[-1])]

    def classify_batch(self, texts, contexts=None):
        return [self.classify(t) for t in texts]


def _dataset(golds, name="d"):
    cases = [
        Case(name=f"c{i}", inputs=CARDSInput(text=f"claim {i}"), expected_output=gold) for i, gold in enumerate(golds)
    ]
    return Dataset(cases=cases, name=name, evaluators=[CARDSOneOfMatch(), CARDSHierarchicalMatch()])


def _row(preds, golds):
    return benchmark_configs({"x": _Fixed(preds)}, {"d": _dataset(golds)}).iloc[0]


def test_failed_predictions_stay_in_the_denominator_and_are_counted():
    row = _row(["1_1", "1_1", "2_2", None], [["1_1"]] * 4)

    assert (row["n_cases"], row["n_failed"]) == (4, 1)
    assert row["exact_match"] == 0.5  # not 2/3: the failed item is wrong, not missing
    assert abs(row["exact_answered"] - 2 / 3) < 1e-3


def test_failed_cases_are_saved_with_an_empty_prediction(tmp_path):
    df = benchmark_configs({"x": _Fixed(["1_1", None])}, {"d": _dataset([["1_1"], ["1_1"]])}, save_dir=str(tmp_path))

    cases = load_run(df.attrs["run_dir"]).cases
    failed = cases[cases["case_id"] == "c1"].iloc[0]
    assert failed["pred"] == "" and failed["exact"] == 0.0 and failed["pred_d1"] == ""
    assert len(cases) == 2


def test_micro_f1_is_plain_accuracy():
    row = _row(["1_1", "1_1", "2_2", "2_2"], [["1_1"]] * 4)
    assert row["exact_match"] == 0.5 and row["micro_f1"] == 0.5


def test_the_two_not_related_spellings_are_one_class():
    row = _row(["0", "0_0"], [["0_0"], ["0_0"]])
    assert row["exact_match"] == 1.0 and row["h_f1"] == 1.0


def test_reliability_columns_are_reported():
    # c0 right, c1 predicted not related, c2 failed, c3 right on an ambiguous gold set
    row = _row(["a_0", "0", None, "b_0"], [["a_0"], ["a_0"], ["a_0"], ["a_0", "b_0"]])

    assert abs(row["not_related_rate"] - 1 / 3) < 1e-3  # one of the three answered predictions
    assert row["n_unambiguous"] == 3 and abs(row["exact_unambiguous"] - 1 / 3) < 1e-3
    assert row["baseline_exact"] == 1.0  # always answering a_0 is right on every case
    assert row["d2_macro_f1_lo"] <= row["d2_macro_f1"] <= row["d2_macro_f1_hi"] or np.isnan(row["d2_macro_f1_lo"])


def test_existing_columns_keep_their_meaning():
    row = _row(["1_1", "2_1"], [["1_1"], ["2_3"]])

    assert row["d2_macro_f1"] == row["macro_f1"]
    assert 0.0 <= row["d1_macro_f1"] <= 1.0
    assert row["h_f1"] == (1.0 + 0.5) / 2  # exact hit, then a same-parent miss worth 0.5


def test_an_empty_dataset_gives_nan_not_zero():
    row = _row([], [])

    assert row["n_cases"] == 0 and np.isnan(row["exact_match"]) and np.isnan(row["h_f1"])
