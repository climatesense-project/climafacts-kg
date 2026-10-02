"""benchmark_configs: interval columns, per-case capture and optional saving (stub classifier, offline)."""

import numpy as np
import pandas as pd
from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import CARDSInput, benchmark_configs
from climafactskg.classifiers.cards.evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch
from climafactskg.classifiers.cards.runs import load_run
from pydantic_evals import Case, Dataset


class _Stub(CARDSClassifierBase):
    """Right (1_1) unless it gets a context, in which case it answers 2_1."""

    _model = "stub-model"
    _provider = "stub-provider"

    def classify(self, text, context=None):
        return "2_1" if context else "1_1"


class _Boom(CARDSClassifierBase):
    def classify(self, text, context=None):
        raise RuntimeError("boom")


def _dataset(contexts):
    cases = [
        Case(name=f"case{i}", inputs=CARDSInput(text=f'claim, "{i}"', context=c), expected_output=["1_1"])
        for i, c in enumerate(contexts)
    ]
    return Dataset(cases=cases, name="d", evaluators=[CARDSOneOfMatch(), CARDSHierarchicalMatch()])


def test_summary_gains_interval_columns_and_keeps_existing_ones():
    df = benchmark_configs({"stub": _Stub()}, {"d": _dataset([None, None, None, None])})

    for col in ("config", "dataset", "context", "n_cases", "exact_match", "h_f1", "d2_macro_f1", "error"):
        assert col in df.columns
    row = df.iloc[0]
    assert row["exact_match"] == 1.0
    assert row["exact_lo"] == row["exact_hi"] == 1.0  # every case right -> degenerate interval


def test_nothing_is_saved_without_save_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = benchmark_configs({"stub": _Stub()}, {"d": _dataset([None])})

    assert "run_dir" not in df.attrs
    assert list(tmp_path.iterdir()) == []


def test_save_dir_writes_a_loadable_run_with_per_case_rows(tmp_path):
    df = benchmark_configs({"stub": _Stub()}, {"d": _dataset(["ctx a", None, "ctx c"])}, save_dir=str(tmp_path))

    run = load_run(df.attrs["run_dir"])
    assert set(run.cases["context"]) == {"none", "with"}
    assert len(run.cases) == 6  # 3 cases x 2 modes
    by_mode = run.cases.groupby("context")
    assert list(by_mode.get_group("none")["has_context"]) == [
        True,
        False,
        True,
    ]  # the case carries context in both runs
    assert list(by_mode.get_group("none")["pred"]) == ["1_1", "1_1", "1_1"]
    assert list(by_mode.get_group("with")["pred"]) == ["2_1", "1_1", "2_1"]
    assert run.cases["text"].iloc[0] == 'claim, "0"'  # commas and quotes survive
    assert run.meta["datasets"] == [{"name": "d", "n_cases": 3, "n_with_context": 2}]
    assert run.meta["configs"][0]["label"] == "stub"
    saved = run.summary.set_index("context")["exact_match"]
    assert saved["none"] == 1.0 and abs(saved["with"] - 1 / 3) < 1e-3


def test_failed_combination_is_saved_flagged_without_case_rows(tmp_path):
    df = benchmark_configs({"boom": _Boom()}, {"d": _dataset([None])}, save_dir=str(tmp_path))

    run = load_run(df.attrs["run_dir"])
    assert run.cases.empty
    assert run.summary.loc[0, "error"] == "boom"
    assert np.isnan(run.summary.loc[0, "exact_match"])


def test_unwritable_save_dir_logs_a_warning_and_still_returns_results(tmp_path, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")

    df = benchmark_configs({"stub": _Stub()}, {"d": _dataset([None])}, save_dir=str(blocker / "runs"))

    assert isinstance(df, pd.DataFrame) and len(df) == 1
    assert "run_dir" not in df.attrs
    assert any("Could not save" in record.message for record in caplog.records)


class _Sized(_Stub):
    _model = "qwen/qwen3-235b-a22b-2507"


def test_model_size_is_recorded_in_run_json_from_the_model_id(tmp_path):
    df = benchmark_configs({"big": _Sized(), "plain": _Stub()}, {"d": _dataset([None, None])}, save_dir=str(tmp_path))

    configs = {c["label"]: c for c in load_run(df.attrs["run_dir"]).meta["configs"]}
    assert (configs["big"]["size_b"], configs["big"]["active_b"]) == (235.0, 22.0)
    assert configs["plain"]["size_b"] is None  # "stub-model" has no published size


def test_an_explicit_size_overrides_the_id_and_fills_in_unknown_sizes(tmp_path):
    df = benchmark_configs(
        {"big": _Sized(), "plain": _Stub()},
        {"d": _dataset([None, None])},
        save_dir=str(tmp_path),
        config_meta={"big": {"size_b": 100.0, "active_b": None}, "plain": {"size_b": 12.0}},
    )

    configs = {c["label"]: c for c in load_run(df.attrs["run_dir"]).meta["configs"]}
    assert (configs["big"]["size_b"], configs["big"]["active_b"]) == (100.0, None)
    assert configs["plain"]["size_b"] == 12.0
