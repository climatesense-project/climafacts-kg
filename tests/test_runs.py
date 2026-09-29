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
    context_effect,
    load_run,
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

    def test_changed_cases_lists_fixed_and_broken(self):
        changed = changed_cases(self._cases())
        assert sorted(zip(changed["case_id"], changed["change"], strict=True)) == [("c1", "fixed"), ("c2", "broken")]

    def test_changed_cases_respects_the_limit(self):
        assert len(changed_cases(self._cases(), limit=1)) == 1
