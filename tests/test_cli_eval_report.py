"""Tests for climafactskg.cli's `eval-report` command."""

import pandas as pd
from climafactskg.classifiers.cards.runs import CASE_COLUMNS, BenchmarkRun, save_run
from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _saved_run(base):
    summary = pd.DataFrame(
        [
            {
                "config": "m",
                "dataset": "d",
                "context": "none",
                "n_with_context": 0,
                "n_cases": 2,
                "exact_match": 0.5,
                "h_f1": 0.6,
                "d1_macro_f1": 0.5,
                "d2_macro_f1": 0.3,
                "error": "",
            }
        ]
    )
    cases = pd.DataFrame(
        [
            {
                "config": "m",
                "dataset": "d",
                "context": "none",
                "case_id": "c1",
                "text": "t",
                "gold": "1_1",
                "pred": "1_1",
                "exact": 1.0,
                "hf1": 1.0,
                "has_context": False,
                "gold_d1": "1",
                "pred_d1": "1",
            }
        ],
        columns=list(CASE_COLUMNS),
    )
    return save_run(BenchmarkRun(meta={"datasets": [], "configs": []}, summary=summary, cases=cases), base)


def test_writes_the_report_next_to_the_run_by_default(tmp_path):
    run_dir = _saved_run(tmp_path)

    result = runner.invoke(app, ["eval-report", str(run_dir)])

    assert result.exit_code == 0
    assert (run_dir / "report.html").is_file()


def test_out_option_sets_the_destination_and_merges_runs(tmp_path):
    first, second = _saved_run(tmp_path), _saved_run(tmp_path)
    out = tmp_path / "combined.html"

    result = runner.invoke(app, ["eval-report", str(first), str(second), "--out", str(out)])

    assert result.exit_code == 0
    assert out.is_file() and "run(s)" in out.read_text(encoding="utf-8")


def test_a_directory_that_is_not_a_run_fails_cleanly(tmp_path):
    result = runner.invoke(app, ["eval-report", str(tmp_path)])

    assert result.exit_code != 0
    assert not (tmp_path / "report.html").exists()
