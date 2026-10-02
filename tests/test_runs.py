"""Tests for saved benchmark runs: persistence, bootstrap intervals and paired context analysis."""

import json

import numpy as np
import pandas as pd
import pytest
from climafactskg.classifiers.cards.runs import (
    CASE_COLUMNS,
    BenchmarkRun,
    bootstrap_ci,
    changed_cases,
    compare_configs,
    context_effect,
    load_run,
    mcnemar_exact,
    model_size_from_id,
    save_run,
)


def _case(config="m", dataset="d", context="none", case_id="c1", exact=1.0, has_context=True, **over):
    row = {
        "config": config,
        "dataset": dataset,
        "context": context,
        "case_id": case_id,
        "text": f"claim {case_id}",
        "gold": "1_1",
        "pred": "1_1",
        "exact": exact,
        "hf1": exact,
        "has_context": has_context,
        "gold_d1": "1",
        "pred_d1": "1",
    }
    row.update(over)
    return row


def _run(cases, meta=None):
    summary = pd.DataFrame(
        [{"config": "m", "dataset": "d", "context": "none", "n_cases": len(cases), "exact_match": 0.5, "h_f1": 0.6}]
    )
    return BenchmarkRun(meta=meta or {"note": "x"}, summary=summary, cases=pd.DataFrame(cases, columns=CASE_COLUMNS))


class TestSaveLoad:
    def test_round_trip_preserves_data_and_adds_run_identity(self, tmp_path):
        text = 'He said, "no, it\'s wrong"\nsecond line, with éè unicode'
        run = _run([_case(case_id="a", text=text), _case(case_id="b", exact=0.0, has_context=False)])

        path = save_run(run, tmp_path)
        loaded = load_run(path)

        assert loaded.meta["note"] == "x"
        assert loaded.meta["run_id"] == path.name
        assert "created_at" in loaded.meta
        assert loaded.cases.loc[0, "text"] == text
        assert list(loaded.cases["case_id"]) == ["a", "b"]
        assert list(loaded.cases["has_context"]) == [True, False]
        assert loaded.cases["has_context"].dtype == bool
        assert loaded.summary.loc[0, "exact_match"] == 0.5

    def test_every_save_gets_its_own_directory(self, tmp_path):
        first = save_run(_run([_case()]), tmp_path)
        second = save_run(_run([_case()]), tmp_path)
        assert first != second and first.is_dir() and second.is_dir()

    def test_no_temporary_files_are_left_behind(self, tmp_path):
        path = save_run(_run([_case()]), tmp_path)
        assert sorted(p.name for p in path.iterdir()) == ["cases.csv", "run.json", "summary.csv"]

    def test_run_without_case_rows_saves_and_loads(self, tmp_path):
        run = _run([], meta={"note": "failed combo"})
        run.summary = pd.DataFrame(
            [
                {
                    "config": "m",
                    "dataset": "d",
                    "context": "none",
                    "n_cases": 0,
                    "exact_match": float("nan"),
                    "h_f1": float("nan"),
                    "error": "boom",
                }
            ]
        )
        loaded = load_run(save_run(run, tmp_path))
        assert loaded.cases.empty
        assert loaded.summary.loc[0, "error"] == "boom"

    def test_missing_file_is_a_clear_error(self, tmp_path):
        (tmp_path / "run.json").write_text(json.dumps({}))
        with pytest.raises(ValueError, match="cases.csv"):
            load_run(tmp_path)

    def test_missing_columns_are_a_clear_error(self, tmp_path):
        path = save_run(_run([_case()]), tmp_path)
        pd.read_csv(path / "cases.csv").drop(columns=["pred"]).to_csv(path / "cases.csv", index=False)
        with pytest.raises(ValueError, match="pred"):
            load_run(path)


class TestBootstrapCi:
    def test_is_deterministic_for_a_fixed_seed(self):
        values = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1]
        assert bootstrap_ci(values) == bootstrap_ci(values)

    def test_brackets_the_mean(self):
        values = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1]
        lo, hi = bootstrap_ci(values)
        assert lo <= np.mean(values) <= hi
        assert 0.0 <= lo < hi <= 1.0

    def test_degenerate_inputs(self):
        assert bootstrap_ci([1.0, 1.0, 1.0]) == (1.0, 1.0)
        assert bootstrap_ci([0.3]) == (0.3, 0.3)
        lo, hi = bootstrap_ci([])
        assert np.isnan(lo) and np.isnan(hi)

    def test_nan_values_are_ignored(self):
        assert bootstrap_ci([1.0, float("nan"), 1.0]) == (1.0, 1.0)


class TestContextEffect:
    def _cases(self):
        rows = []
        # c1: wrong without, right with (fixed); c2: right without, wrong with (broken); c3: unchanged right;
        # c4: unchanged wrong; c5 has no context (excluded from the paired comparison).
        for cid, none_exact, with_exact, has_ctx in (
            ("c1", 0.0, 1.0, True),
            ("c2", 1.0, 0.0, True),
            ("c3", 1.0, 1.0, True),
            ("c4", 0.0, 0.0, True),
            ("c5", 1.0, 1.0, False),
        ):
            rows.append(_case(context="none", case_id=cid, exact=none_exact, has_context=has_ctx))
            rows.append(_case(context="with", case_id=cid, exact=with_exact, has_context=has_ctx))
        return pd.DataFrame(rows, columns=CASE_COLUMNS)

    def test_counts_are_paired_on_covered_cases_only(self):
        eff = context_effect(self._cases())

        assert len(eff) == 1
        row = eff.iloc[0]
        assert (row["n_paired"], row["fixed"], row["broken"], row["unchanged"]) == (4, 1, 1, 2)
        assert row["exact_none"] == 0.5 and row["exact_with"] == 0.5 and row["delta"] == 0.0

    def test_no_with_rows_gives_an_empty_frame(self):
        cases = pd.DataFrame([_case(context="none")], columns=CASE_COLUMNS)
        eff = context_effect(cases)
        assert eff.empty
        assert "delta" in eff.columns

    def test_empty_case_frame_gives_empty_results_without_raising(self):
        empty = pd.DataFrame(columns=list(CASE_COLUMNS))

        assert context_effect(empty).empty
        assert changed_cases(empty).empty

    def test_changed_cases_lists_fixed_and_broken(self):
        changed = changed_cases(self._cases())
        assert sorted(zip(changed["case_id"], changed["change"], strict=True)) == [("c1", "fixed"), ("c2", "broken")]

    def test_changed_cases_respects_the_limit(self):
        assert len(changed_cases(self._cases(), limit=1)) == 1


class TestRoundTripEdgeStrings:
    def test_empty_text_and_na_like_labels_survive(self, tmp_path):
        run = _run([_case(config="None", dataset="NA", case_id="a", text="")])
        run.summary = pd.DataFrame(
            [{"config": "None", "dataset": "NA", "context": "none", "n_cases": 1, "exact_match": 0.5, "h_f1": 0.5}]
        )

        loaded = load_run(save_run(run, tmp_path))

        assert loaded.cases.loc[0, "text"] == ""
        assert loaded.cases.loc[0, "config"] == "None" and loaded.cases.loc[0, "dataset"] == "NA"
        assert loaded.summary.loc[0, "config"] == "None" and loaded.summary.loc[0, "dataset"] == "NA"

    def test_missing_scores_stay_missing(self, tmp_path):
        run = _run([_case(case_id="a", exact=float("nan"))])
        loaded = load_run(save_run(run, tmp_path))
        assert np.isnan(loaded.cases.loc[0, "exact"])


class TestChangedCasesCap:
    def test_limit_applies_per_config_and_dataset(self):
        rows = []
        for dataset in ("d1", "d2"):
            for i in range(3):
                rows.append(_case(dataset=dataset, context="none", case_id=f"c{i}", exact=0.0))
                rows.append(_case(dataset=dataset, context="with", case_id=f"c{i}", exact=1.0))
        changed = changed_cases(pd.DataFrame(rows, columns=CASE_COLUMNS), limit=2)

        assert len(changed) == 4
        assert changed.groupby("dataset").size().tolist() == [2, 2]


class TestMcNemarExact:
    def test_known_values(self):
        assert mcnemar_exact(0, 0) == 1.0
        assert mcnemar_exact(5, 0) == pytest.approx(0.0625)  # 2 * (1/2)^5
        assert mcnemar_exact(3, 3) == 1.0
        assert mcnemar_exact(10, 21) == pytest.approx(mcnemar_exact(21, 10))

    def test_agrees_with_scipys_exact_binomial_test(self):
        stats = pytest.importorskip("scipy.stats")
        for better, worse in ((10, 21), (2, 9), (0, 6), (14, 14), (40, 25)):
            expected = stats.binomtest(min(better, worse), better + worse, 0.5).pvalue
            assert mcnemar_exact(better, worse) == pytest.approx(expected)

    def test_never_exceeds_one(self):
        assert mcnemar_exact(1, 1) == 1.0


def _effect_frame(fixed, broken, same_right, same_wrong):
    rows = []
    spec = [(0.0, 1.0)] * fixed + [(1.0, 0.0)] * broken + [(1.0, 1.0)] * same_right + [(0.0, 0.0)] * same_wrong
    for i, (none_exact, with_exact) in enumerate(spec):
        rows.append(_case(context="none", case_id=f"c{i}", exact=none_exact))
        rows.append(_case(context="with", case_id=f"c{i}", exact=with_exact))
    return pd.DataFrame(rows, columns=CASE_COLUMNS)


class TestContextEffectSignificance:
    def test_reports_a_paired_interval_and_an_exact_p_value(self):
        eff = context_effect(_effect_frame(fixed=8, broken=0, same_right=4, same_wrong=0)).iloc[0]

        assert (eff["n_paired"], eff["fixed"], eff["broken"]) == (12, 8, 0)
        assert eff["p_value"] == pytest.approx(2 * 0.5**8)
        assert eff["delta_lo"] > 0 and eff["delta_lo"] <= eff["delta"] <= eff["delta_hi"]

    def test_a_balanced_change_is_not_significant(self):
        eff = context_effect(_effect_frame(fixed=10, broken=10, same_right=5, same_wrong=5)).iloc[0]

        assert eff["p_value"] == 1.0 and eff["delta"] == 0.0
        assert eff["delta_lo"] < 0 < eff["delta_hi"]

    def test_the_real_v2_shape_ten_fixed_twenty_one_broken(self):
        eff = context_effect(_effect_frame(fixed=10, broken=21, same_right=40, same_wrong=72)).iloc[0]

        assert eff["p_value"] == pytest.approx(mcnemar_exact(10, 21))
        assert 0.05 < eff["p_value"] < 0.1  # suggestive, not significant at 0.05
        assert eff["delta_lo"] < -0.1 and eff["delta_hi"] <= 0.01  # the interval just reaches zero

    def test_empty_frame_has_the_new_columns(self):
        eff = context_effect(pd.DataFrame(columns=list(CASE_COLUMNS)))
        assert {"delta_lo", "delta_hi", "p_value"} <= set(eff.columns)


def _config_rows(config, right_ids, all_ids, dataset="d", context="none"):
    return [
        _case(config=config, dataset=dataset, context=context, case_id=cid, exact=1.0 if cid in right_ids else 0.0)
        for cid in all_ids
    ]


class TestCompareConfigs:
    def _cases(self):
        ids = [f"c{i}" for i in range(10)]
        rows = _config_rows("A", ids[:5], ids)
        rows += _config_rows("B", ids[:9], ids)  # B fixes four cases A gets wrong
        rows += _config_rows("C", ids[:3], ids)  # C breaks two cases A gets right
        return pd.DataFrame(rows, columns=CASE_COLUMNS)

    def test_each_config_is_compared_with_the_baseline_on_the_same_cases(self):
        out = compare_configs(self._cases(), baseline="A").set_index("config")

        b, c = out.loc["B"], out.loc["C"]
        assert (b["n_paired"], b["better"], b["worse"]) == (10, 4, 0)
        assert b["exact_baseline"] == 0.5 and b["exact_config"] == 0.9 and b["delta"] == pytest.approx(0.4)
        assert b["p_value"] == pytest.approx(2 * 0.5**4)
        assert (c["better"], c["worse"]) == (0, 2) and c["delta"] == pytest.approx(-0.2)
        assert set(out["baseline"]) == {"A"}

    def test_only_cases_both_configs_answered_are_paired(self):
        ids = [f"c{i}" for i in range(10)]
        rows = _config_rows("A", ids[:5], ids) + _config_rows("D", ids[:4], ids[:4])
        out = compare_configs(pd.DataFrame(rows, columns=CASE_COLUMNS), baseline="A")

        assert out.iloc[0]["n_paired"] == 4

    def test_datasets_are_compared_separately(self):
        ids = [f"c{i}" for i in range(4)]
        rows = _config_rows("A", ids[:2], ids, dataset="d1") + _config_rows("B", ids, ids, dataset="d1")
        rows += _config_rows("A", ids, ids, dataset="d2") + _config_rows("B", ids[:2], ids, dataset="d2")
        out = compare_configs(pd.DataFrame(rows, columns=CASE_COLUMNS), baseline="A").set_index("dataset")

        assert out.loc["d1", "delta"] > 0 and out.loc["d2", "delta"] < 0

    def test_the_context_mode_is_selected(self):
        ids = [f"c{i}" for i in range(4)]
        rows = _config_rows("A", ids[:2], ids) + _config_rows("B", ids, ids, context="with")
        out = compare_configs(pd.DataFrame(rows, columns=CASE_COLUMNS), baseline="A", context="none")

        assert out.empty  # B has no "none" rows, so nothing to pair

    def test_unknown_baseline_is_a_clear_error(self):
        with pytest.raises(ValueError, match="baseline"):
            compare_configs(self._cases(), baseline="nope")

    def test_a_lone_baseline_gives_an_empty_frame_with_columns(self):
        ids = ["c0", "c1"]
        out = compare_configs(pd.DataFrame(_config_rows("A", ids, ids), columns=CASE_COLUMNS), baseline="A")

        assert out.empty and {"delta", "p_value", "better", "worse"} <= set(out.columns)


class TestModelSizeFromId:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("meta-llama/llama-3.3-70b-instruct", (70.0, None)),
            ("openai/gpt-oss-120b", (120.0, None)),
            ("openai/gpt-oss-20b:batch", (20.0, None)),
            ("qwen/qwen3-235b-a22b-2507", (235.0, 22.0)),
            ("qwen/qwen3.6-35b-a3b", (35.0, 3.0)),
            ("qwen/qwen3-30b-a3b-instruct-2507", (30.0, 3.0)),
            ("nvidia/nemotron-3-super-120b-a12b", (120.0, 12.0)),
            ("mistralai/mistral-small-3.2-24b-instruct", (24.0, None)),
            ("google/gemma-4-31b-it", (31.0, None)),
            ("meta-llama/llama-3.1-8b-instruct", (8.0, None)),
            ("qwen/qwen3-8b:nitro", (8.0, None)),
            ("some/tiny-0.6b", (0.6, None)),
        ],
    )
    def test_the_parameter_count_is_read_from_the_model_id(self, model, expected):
        assert model_size_from_id(model) == expected

    @pytest.mark.parametrize(
        "model",
        [
            "openai/gpt-4o-mini",  # "4o" is not a size
            "openai/gpt-5.2",
            "deepseek/deepseek-v4-pro",
            "minimax/minimax-m2.7",
            "z-ai/glm-4.7-flash",
            "mistralai/mistral-nemo",
            "meta-llama/llama-4-maverick",
            "",
            None,
        ],
    )
    def test_an_id_without_a_published_size_gives_none(self, model):
        assert model_size_from_id(model) == (None, None)
