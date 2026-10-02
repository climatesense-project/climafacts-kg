"""Tests for climafactskg.cli's `eval` command (datasets, classifiers and the benchmark are stubbed)."""

from types import SimpleNamespace

import pandas as pd
import pytest
from climafactskg.classifiers.cards import eval as cards_eval
from climafactskg.classifiers.cards import report, runconfig
from climafactskg.classifiers.cards.datasets import CARDSInput
from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()

PAID = """
[run]
save_dir = "{save}"

[[classifiers]]
label = "gpt"
provider = "openrouter"
model = "openai/gpt-4o-mini"

[[datasets]]
name = "climatesense_v2"
"""
FREE = PAID.replace('provider = "openrouter"', 'provider = "ollama"')


def _dataset(contexts):
    cases = [SimpleNamespace(inputs=CARDSInput(text=f"claim {i}", context=c)) for i, c in enumerate(contexts)]
    return SimpleNamespace(cases=cases)


@pytest.fixture
def stubs(monkeypatch, tmp_path):
    calls = {"benchmark": [], "classifiers": [], "report": []}
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(runconfig, "build_dataset", lambda spec: _dataset(["ctx", "ctx", None, None]))

    class _Clf:
        def __init__(self, label):
            self.label = label

        def count_cached(self, texts, contexts=None):
            return calls.get("cached", 0)

        def __eq__(self, other):
            return other == f"clf:{self.label}"

    def build_classifier(spec):
        calls["classifiers"].append(spec.label)
        return _Clf(spec.label)

    def benchmark(configs, datasets, **kwargs):
        calls["benchmark"].append((configs, datasets, kwargs))
        df = pd.DataFrame([{"config": "gpt", "dataset": "climatesense_v2", "context": "none", "n_cases": 4}])
        df.attrs["run_dir"] = str(run_dir)
        return df

    monkeypatch.setattr(runconfig, "build_classifier", build_classifier)
    monkeypatch.setattr(cards_eval, "benchmark_configs", benchmark)
    monkeypatch.setattr(cards_eval, "print_benchmark", lambda df, *a, **k: None)
    monkeypatch.setattr(report, "render_html", lambda runs, out, baseline=None: calls["report"].append(out) or out)
    monkeypatch.setattr("climafactskg.classifiers.cards.runs.load_run", lambda path: SimpleNamespace(path=path))
    calls["run_dir"] = run_dir
    return calls


def _config(tmp_path, template):
    path = tmp_path / "eval.toml"
    path.write_text(template.format(save=tmp_path / "runs"), encoding="utf-8")
    return str(path)


def test_dry_run_prints_the_plan_and_builds_nothing(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID), "--dry-run"])

    assert result.exit_code == 0
    assert "gpt" in result.output and "climatesense_v2" in result.output
    assert "8" in result.output  # 4 cases x 2 context modes x 1 paid classifier
    assert stubs["benchmark"] == []


def test_a_paid_run_needs_confirmation(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID)], input="n\n")

    assert result.exit_code == 1
    assert stubs["benchmark"] == []


def test_a_confirmed_paid_run_executes_and_saves_the_config(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID)], input="y\n")

    assert result.exit_code == 0, result.output
    ((configs, datasets, kwargs),) = stubs["benchmark"]
    assert configs == {"gpt": "clf:gpt"} and list(datasets) == ["climatesense_v2"]
    assert kwargs["context_modes"] == ["none", "with"] and kwargs["save_dir"] == str(tmp_path / "runs")
    assert kwargs["category_scores"] == "all"
    assert (stubs["run_dir"] / "config.toml").read_text(encoding="utf-8").startswith("\n[run]")


def test_yes_skips_the_confirmation(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID), "--yes"])

    assert result.exit_code == 0 and len(stubs["benchmark"]) == 1


def test_a_free_run_never_asks(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, FREE)])

    assert result.exit_code == 0 and len(stubs["benchmark"]) == 1


def test_report_flag_writes_the_html_report_in_the_run_dir(stubs, tmp_path):
    result = runner.invoke(app, ["eval", "run", _config(tmp_path, FREE), "--report"])

    assert result.exit_code == 0
    assert stubs["report"] == [str(stubs["run_dir"] / "report.html")]


def test_an_invalid_config_exits_with_the_reason(stubs, tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('[[classifiers]]\nlabel = "a"\nmodle = "x"\n', encoding="utf-8")

    result = runner.invoke(app, ["eval", "run", str(path)])

    assert result.exit_code == 1
    assert stubs["benchmark"] == []


def test_eval_is_a_command_group_with_run_context_and_report():
    result = runner.invoke(app, ["eval", "--help"])

    assert result.exit_code == 0
    for name in ("run", "context", "report"):
        assert name in result.output


def test_the_2_2_0_command_names_still_work_but_are_hidden():
    top = runner.invoke(app, ["--help"])
    old = runner.invoke(app, ["eval-report", "--help"])

    assert "eval-report" not in top.output and "eval-context" not in top.output
    assert old.exit_code == 0


def test_a_missing_eval_extra_gives_an_install_hint(stubs, tmp_path, monkeypatch, caplog):
    def missing(spec):
        raise ModuleNotFoundError("No module named 'pydantic_evals'", name="pydantic_evals")

    monkeypatch.setattr(runconfig, "build_dataset", missing)

    result = runner.invoke(app, ["eval", "run", _config(tmp_path, FREE)])

    assert result.exit_code == 1
    assert "climafactskg[eval]" in caplog.text


def test_the_plan_separates_cached_from_new_paid_calls(stubs, tmp_path):
    stubs["cached"] = 3  # of the 4 cases per mode; counted for the "none" and the "with" mode

    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID), "--dry-run"])

    assert result.exit_code == 0
    assert "6 already cached" in result.output and "2 new" in result.output
    assert stubs["benchmark"] == []


def test_the_plan_falls_back_to_an_upper_bound_when_the_classifier_cannot_be_built(stubs, tmp_path, monkeypatch):
    def broken(spec):
        raise RuntimeError("no API key")

    monkeypatch.setattr(runconfig, "build_classifier", broken)

    result = runner.invoke(app, ["eval", "run", _config(tmp_path, PAID), "--dry-run"])

    assert result.exit_code == 0 and "up to 8" in result.output
