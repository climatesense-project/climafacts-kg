# Saved, Comparable and Visual Eval Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save every benchmark run as tidy data, print a compact readable comparison in the terminal, and generate a self-contained HTML report with inline SVG charts, without adding a dependency.

**Architecture:** A new `runs.py` owns persistence (`BenchmarkRun`, `save_run`, `load_run`), bootstrap intervals and paired context analysis. `benchmark_configs` captures per-case rows and interval columns, and optionally saves. A new `report.py` builds the HTML with plain Python string building (no jinja2, no JS, no CDN). A `climafactskg eval-report` command wires it up.

**Tech Stack:** Python 3.12, pandas/numpy (existing), rich (existing), typer, pytest, ruff. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-29-eval-reporting-design.md`

## Global Constraints

- No new dependency: numpy comes with pandas; **do not use jinja2** (it is only a transitive dependency); charts are inline SVG, no JS, no CDN, no external URLs.
- `benchmark_configs` keeps returning the same DataFrame (same existing columns and rows); nothing is saved unless `save_dir` is given; a failed save logs a warning and never loses the DataFrame.
- Bootstrap: 95% percentile interval, deterministic (`seed=0`, `n_boot=2000`), on the per-case scores.
- Compact terminal table must fit 80 columns; scores print as `0.378±0.08` (value ± half-width of the interval).
- Charts: at most 8 series; categorical colours from the dataviz reference palette, validated in both modes (light `#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4,#008300,#4a3aa7,#e34948`; dark `#3987e5,#d95926,#199e70,#c98500,#d55181,#008300,#9085e9,#e66767`); surfaces light `#fcfcfb` / dark `#1a1a19`; bars at most 24px thick, 4px rounded data end, square baseline, 2px surface gap between adjacent bars, hairline solid grid, text in text tokens (never the series colour), a legend for two or more series, values labelled only on the best bar per group, native `<title>` hover on every bar, table view for exact numbers. Three light slots are below 3:1 contrast; the comparison table is the required relief.
- Every user-supplied string (config labels, claims, gold/predictions, errors) is HTML-escaped in the report.
- Style: Google docstrings, 120-char lines, `ruff check` and `ruff format` clean, `zip(..., strict=True)` for parallel lists. Tests are offline. Commits are Conventional Commits with **no** `Co-Authored-By` trailer.
- Run tools via uv from the repo root: `uv run pytest ...`, `uv run ruff ...` (unset `VIRTUAL_ENV` first if it points at another environment).

## Review Focus

- Claim text containing commas, quotes, newlines and non-ASCII must survive `cases.csv` save/load unchanged.
- A failed combination (summary row with an `error` and no case rows) must save, load and render (flagged) without raising.
- NaN metrics or `n_cases == 0` must show `—` in tables and omit the bar, never crash or print `nan`.
- Two runs with identical config labels must not collide or duplicate series in the report (run suffix).
- HTML special characters in claims and labels (`<script>`, `&`, quotes) must be escaped in the report.
- The compact table must stay within 80 columns even with long config and dataset labels (truncate, never overflow).

## Spec deviations (decided while planning; the spec is updated in Task 5)

- `benchmark_configs` keeps its loop in place and captures per-case rows there instead of extracting a `_run_combo` helper: same result, much smaller diff to code that has tests.
- The compact terminal table shows `0.378±0.08` instead of `0.378 [0.30-0.46]` so it fits 80 columns; the HTML report shows the full interval.
- The report is built with plain Python strings, not jinja2 (transitive dependency only).

---

## File Structure

- Create `climafactskg/classifiers/cards/runs.py`: `BenchmarkRun`, `CASE_COLUMNS`, `bootstrap_ci`, `save_run`, `load_run`, `context_effect`, `changed_cases`, `collect_meta`.
- Modify `climafactskg/classifiers/cards/eval.py`: capture case rows and intervals, `save_dir`, compact `print_benchmark`, `print_context_effect`.
- Create `climafactskg/classifiers/cards/report.py`: `bar_chart_svg`, `render_html`.
- Modify `climafactskg/cli.py`: `eval-report` command.
- Modify `.gitignore`, `CLAUDE.md`, the spec.
- Create `tests/test_runs.py`, `tests/test_benchmark_saving.py`, `tests/test_report.py`, `tests/test_cli_eval_report.py`; extend `tests/test_eval_context.py`.

---

### Task 1: `runs.py` (persistence, intervals, paired context analysis)

**Files:**
- Create: `climafactskg/classifiers/cards/runs.py`
- Create: `tests/test_runs.py`
- Modify: `.gitignore` (add `data/eval_runs/`)

**Interfaces:**
- Produces:
  - `CASE_COLUMNS: tuple[str, ...]` = `("config","dataset","context","case_id","text","gold","pred","exact","hf1","has_context","gold_d1","pred_d1")`
  - `@dataclass BenchmarkRun(meta: dict, summary: pd.DataFrame, cases: pd.DataFrame, path: Path | None = None)`
  - `bootstrap_ci(values, n_boot=2000, seed=0, level=0.95) -> tuple[float, float]`
  - `save_run(run: BenchmarkRun, base_dir, now: datetime | None = None) -> Path`
  - `load_run(path) -> BenchmarkRun` (raises `ValueError` on missing files/columns)
  - `context_effect(cases: pd.DataFrame) -> pd.DataFrame` columns `config, dataset, n_paired, exact_none, exact_with, delta, fixed, broken, unchanged`
  - `changed_cases(cases: pd.DataFrame, limit: int = 20) -> pd.DataFrame` columns `config, dataset, case_id, text, gold, pred_none, pred_with, change`
  - `collect_meta(datasets, context_modes, min_context_coverage, configs) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_runs.py`:

```python
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
            [{"config": "m", "dataset": "d", "context": "none", "n_cases": 0, "exact_match": float("nan"),
              "h_f1": float("nan"), "error": "boom"}]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_runs.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'climafactskg.classifiers.cards.runs'`.

- [ ] **Step 3: Write the implementation**

Create `climafactskg/classifiers/cards/runs.py`:

```python
"""Saved CARDS benchmark runs: persistence, bootstrap intervals and paired context analysis."""

import json
import logging
import os
import subprocess
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CASE_COLUMNS = (
    "config",
    "dataset",
    "context",
    "case_id",
    "text",
    "gold",
    "pred",
    "exact",
    "hf1",
    "has_context",
    "gold_d1",
    "pred_d1",
)
_SUMMARY_REQUIRED = ("config", "dataset", "context", "n_cases", "exact_match", "h_f1")
_RUN_FILES = ("run.json", "cases.csv", "summary.csv")
_EFFECT_COLUMNS = ("config", "dataset", "n_paired", "exact_none", "exact_with", "delta", "fixed", "broken", "unchanged")
_CHANGED_COLUMNS = ("config", "dataset", "case_id", "text", "gold", "pred_none", "pred_with", "change")


@dataclass
class BenchmarkRun:
    """One benchmark run: metadata, the summary table and the tidy per-case rows."""

    meta: dict[str, Any]
    summary: pd.DataFrame
    cases: pd.DataFrame
    path: Path | None = None


def bootstrap_ci(values: Iterable[float], n_boot: int = 2000, seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    """Deterministic percentile bootstrap interval of the mean of *values* (NaNs ignored).

    Returns ``(nan, nan)`` for no data and ``(v, v)`` when there is a single distinct value.
    """
    arr = np.asarray(list(values), dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (float("nan"), float("nan"))
    if arr.size == 1 or bool(np.all(arr == arr[0])):
        return (float(arr[0]), float(arr[0]))
    rng = np.random.default_rng(seed)
    means = arr[rng.integers(0, arr.size, size=(n_boot, arr.size))].mean(axis=1)
    lo, hi = np.percentile(means, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return (float(lo), float(hi))


def _write_atomic(path: Path, write) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save_run(run: BenchmarkRun, base_dir: str | Path, now: datetime | None = None) -> Path:
    """Writes *run* to a new ``<base_dir>/<UTC timestamp>-<id>/`` directory and returns it.

    An existing directory is never overwritten. Each file is written atomically. ``run.meta`` gains ``run_id`` and
    ``created_at``, and ``run.path`` is set.
    """
    created = now or datetime.now(timezone.utc)
    run_id = f"{created:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    target = Path(base_dir) / run_id
    target.mkdir(parents=True, exist_ok=False)
    meta = {**run.meta, "run_id": run_id, "created_at": created.isoformat()}
    _write_atomic(target / "run.json", lambda p: p.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8"))
    _write_atomic(target / "cases.csv", lambda p: run.cases.to_csv(p, index=False))
    _write_atomic(target / "summary.csv", lambda p: run.summary.to_csv(p, index=False))
    run.meta, run.path = meta, target
    return target


def load_run(path: str | Path) -> BenchmarkRun:
    """Loads a saved run, validating that its files and required columns exist (``ValueError`` otherwise)."""
    directory = Path(path)
    for name in _RUN_FILES:
        if not (directory / name).is_file():
            raise ValueError(f"{directory}: missing {name}; not a saved benchmark run")
    meta = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    cases = pd.read_csv(
        directory / "cases.csv",
        dtype={"case_id": str, "text": str, "gold": str, "pred": str, "gold_d1": str, "pred_d1": str},
        keep_default_na=False,
        na_values=[""],
    )
    missing = [c for c in CASE_COLUMNS if c not in cases.columns]
    if missing:
        raise ValueError(f"{directory}/cases.csv: missing columns {missing}")
    cases["has_context"] = cases["has_context"].astype(bool)
    summary = pd.read_csv(directory / "summary.csv")
    missing = [c for c in _SUMMARY_REQUIRED if c not in summary.columns]
    if missing:
        raise ValueError(f"{directory}/summary.csv: missing columns {missing}")
    if "error" in summary.columns:
        summary["error"] = summary["error"].fillna("")
    return BenchmarkRun(meta=meta, summary=summary, cases=cases, path=directory)


def _paired(cases: pd.DataFrame) -> pd.DataFrame:
    """Rows with the exact score without and with context for the same (config, dataset, case) that has context."""
    covered = cases[cases["has_context"]]
    key = ["config", "dataset", "case_id"]
    none = covered[covered["context"] == "none"][[*key, "exact", "pred", "text", "gold"]]
    with_ = covered[covered["context"] == "with"][[*key, "exact", "pred"]]
    paired = none.merge(with_, on=key, suffixes=("_none", "_with")).dropna(subset=["exact_none", "exact_with"])
    paired["fixed"] = (paired["exact_none"] < 1) & (paired["exact_with"] >= 1)
    paired["broken"] = (paired["exact_none"] >= 1) & (paired["exact_with"] < 1)
    return paired


def context_effect(cases: pd.DataFrame) -> pd.DataFrame:
    """Paired effect of context per (config, dataset), on the cases that actually have context.

    ``fixed``: wrong without context, right with it; ``broken``: the reverse. Empty when nothing is paired.
    """
    paired = _paired(cases)
    if paired.empty:
        return pd.DataFrame(columns=list(_EFFECT_COLUMNS))
    grouped = paired.groupby(["config", "dataset"], as_index=False).agg(
        n_paired=("case_id", "size"),
        exact_none=("exact_none", "mean"),
        exact_with=("exact_with", "mean"),
        fixed=("fixed", "sum"),
        broken=("broken", "sum"),
    )
    grouped["delta"] = grouped["exact_with"] - grouped["exact_none"]
    grouped["unchanged"] = grouped["n_paired"] - grouped["fixed"] - grouped["broken"]
    grouped[["exact_none", "exact_with", "delta"]] = grouped[["exact_none", "exact_with", "delta"]].round(4)
    return grouped[list(_EFFECT_COLUMNS)]


def changed_cases(cases: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    """Cases whose exact-match outcome flipped with context (``change`` is ``fixed`` or ``broken``)."""
    paired = _paired(cases)
    changed = paired[paired["fixed"] | paired["broken"]].copy()
    if changed.empty:
        return pd.DataFrame(columns=list(_CHANGED_COLUMNS))
    changed["change"] = np.where(changed["fixed"], "fixed", "broken")
    return changed[list(_CHANGED_COLUMNS)].head(limit).reset_index(drop=True)


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent,
            check=True,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _package_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("climafactskg")
    except Exception:  # noqa: BLE001 - metadata is best effort
        return None


def collect_meta(
    datasets: dict[str, Any],
    context_modes: Sequence[str],
    min_context_coverage: float,
    configs: list[dict[str, str]],
) -> dict[str, Any]:
    """Run metadata: git commit, package version, dataset sizes (with context counts), configs and options."""

    def n_context(dataset) -> int:
        return sum(1 for case in dataset.cases if getattr(case.inputs, "context", None))

    return {
        "git_commit": _git_commit(),
        "package_version": _package_version(),
        "datasets": [
            {"name": name, "n_cases": len(ds.cases), "n_with_context": n_context(ds)} for name, ds in datasets.items()
        ],
        "configs": configs,
        "context_modes": list(context_modes),
        "min_context_coverage": min_context_coverage,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_runs.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Gitignore, lint, format, commit**

Append to `.gitignore` (next to the other `data/` entries): `data/eval_runs/`.

```bash
uv run ruff check --fix climafactskg/classifiers/cards/runs.py tests/test_runs.py
uv run ruff format climafactskg/classifiers/cards/runs.py tests/test_runs.py
uv run pytest tests -q
git add .gitignore climafactskg/classifiers/cards/runs.py tests/test_runs.py
git commit -m "feat(eval): add saved benchmark runs with bootstrap intervals and paired context analysis"
```

---

### Task 2: Capture per-case rows and intervals in `benchmark_configs`; optional saving

**Files:**
- Modify: `climafactskg/classifiers/cards/eval.py` (imports; `benchmark_configs`)
- Create: `tests/test_benchmark_saving.py`

**Interfaces:**
- Consumes: `BenchmarkRun`, `CASE_COLUMNS`, `bootstrap_ci`, `collect_meta`, `save_run` from Task 1.
- Produces: `benchmark_configs(..., save_dir: str | None = None)`; the returned DataFrame gains `exact_lo`, `exact_hi`, `h_f1_lo`, `h_f1_hi`; `df.attrs["run_dir"]` is the saved directory when saving succeeded.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_benchmark_saving.py`:

```python
"""benchmark_configs: interval columns, per-case capture and optional saving (stub classifier, offline)."""

import numpy as np
import pandas as pd
from pydantic_evals import Case, Dataset

from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import CARDSInput, benchmark_configs
from climafactskg.classifiers.cards.evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch
from climafactskg.classifiers.cards.runs import load_run


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
    assert list(by_mode.get_group("none")["has_context"]) == [True, False, True]  # the case carries context in both runs
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_benchmark_saving.py -v`
Expected: FAIL — `KeyError: 'exact_lo'` / `TypeError: benchmark_configs() got an unexpected keyword argument 'save_dir'`.

- [ ] **Step 3: Write the implementation**

In `climafactskg/classifiers/cards/eval.py`:

1. Add the import after the `from .evaluators import (...)` block:

```python
from .runs import CASE_COLUMNS, BenchmarkRun, bootstrap_ci, collect_meta, save_run
```

2. Change the signature and docstring of `benchmark_configs`: add `save_dir: str | None = None,` as the last parameter and, in `Args:`:

```
        save_dir: When set, the run (metadata, tidy per-case rows and the summary) is saved to a new timestamped
            directory under it (see :mod:`.runs`) and its path is attached as ``df.attrs["run_dir"]``. A failed
            save logs a warning and never loses the returned DataFrame.
```
and in `Returns:` mention the added interval columns `exact_lo`, `exact_hi`, `h_f1_lo`, `h_f1_hi` (95% bootstrap over cases).

3. Right after `rows = []` add `case_rows: list[dict[str, Any]] = []`.

4. In the failure `rows.append({...})` (the `except Exception as exc:` branch) add these keys before `"error"`:

```python
                    "exact_lo": float("nan"),
                    "exact_hi": float("nan"),
                    "h_f1_lo": float("nan"),
                    "h_f1_hi": float("nan"),
```

5. In the success path, replace the `for case in report.cases:` loop so it also records a case row. The loop body currently computes `predicted`, `expected`, `one_of_score`, `h`, and appends to `y_true`/`y_pred`; extend it (keep every existing line) so that, after `y_pred.append(predicted)`, it does:

```python
            charged_label = y_true[-1]
            case_rows.append(
                {
                    "config": config_name,
                    "dataset": dataset_name,
                    "context": mode,
                    "case_id": case.name,
                    "text": case.inputs.text if isinstance(case.inputs, CARDSInput) else str(case.inputs),
                    "gold": ";".join(expected),
                    "pred": predicted,
                    "exact": one_of_score.value if one_of_score is not None else float("nan"),
                    "hf1": h.value if h is not None else float("nan"),
                    "has_context": isinstance(case.inputs, CARDSInput) and bool(case.inputs.context),
                    "gold_d1": project_to_depth(charged_label, 1),
                    "pred_d1": project_to_depth(predicted, 1),
                }
            )
```

Note `h` is only bound by the walrus in the existing `if (h := case.scores.get("CARDSHierarchicalMatch")) is not None:` line; to keep it bound when the score is missing, change that line to:

```python
            h = case.scores.get("CARDSHierarchicalMatch")
            if h is not None:
                hier_scores.append(h.value)
```

6. In the success `rows.append({...})` add, before `"error": ""`:

```python
                "exact_lo": (ci_exact := bootstrap_ci(exact_scores))[0],
                "exact_hi": ci_exact[1],
                "h_f1_lo": (ci_hier := bootstrap_ci(hier_scores))[0],
                "h_f1_hi": ci_hier[1],
```

7. Replace the final `return pd.DataFrame(rows)` with:

```python
    df = pd.DataFrame(rows)
    if save_dir is not None:
        try:
            configs_meta = [
                {
                    "label": name,
                    "provider": str(getattr(clf, "_provider", "")),
                    "model": str(getattr(clf, "_model", type(clf).__name__)),
                    "prompt": _prompt_id(clf),
                }
                for name, clf in configs.items()
            ]
            run = BenchmarkRun(
                meta=collect_meta(datasets, context_modes, min_context_coverage, configs_meta),
                summary=df,
                cases=pd.DataFrame(case_rows, columns=list(CASE_COLUMNS)),
            )
            df.attrs["run_dir"] = str(save_run(run, save_dir))
        except OSError as exc:
            logger.warning("Could not save benchmark run to %s: %s", save_dir, exc)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_benchmark_saving.py tests/test_eval_context.py tests/test_evaluators.py -v` then `uv run pytest tests -q`
Expected: PASS everywhere (existing benchmark tests unchanged).

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg tests && uv run ruff format climafactskg tests
git add climafactskg/classifiers/cards/eval.py tests/test_benchmark_saving.py
git commit -m "feat(eval): save benchmark runs with per-case rows and bootstrap intervals"
```

---

### Task 3: Compact terminal output

**Files:**
- Modify: `climafactskg/classifiers/cards/eval.py` (`print_benchmark`; add `print_context_effect`)
- Modify: `tests/test_eval_context.py`

**Interfaces:**
- Consumes: `context_effect` from Task 1; interval columns from Task 2.
- Produces: `print_benchmark(df, title="Benchmark Results", wide=False)`; `print_context_effect(cases: pd.DataFrame) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_eval_context.py` (add `import io`, `from rich.console import Console`, `from climafactskg.classifiers.cards import eval as eval_module`, `from climafactskg.classifiers.cards.eval import print_context_effect`, and `from climafactskg.classifiers.cards.runs import CASE_COLUMNS` to its imports):

```python
def _capture(monkeypatch, width=80):
    buffer = io.StringIO()
    monkeypatch.setattr(eval_module, "_console", Console(width=width, file=buffer, color_system=None))
    return buffer


def _long_summary():
    return pd.DataFrame(
        [
            {
                "config": "a-very-long-configuration-label-that-overflows",
                "dataset": "a-very-long-dataset-label",
                "context": "with",
                "n_with_context": 143,
                "n_cases": 143,
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "prompt": "# CARDS TAXONOMY REASONING system prompt",
                "exact_match": 0.378,
                "exact_lo": 0.30,
                "exact_hi": 0.46,
                "h_f1": 0.6084,
                "h_f1_lo": 0.55,
                "h_f1_hi": 0.66,
                "d1_macro_f1": 0.6848,
                "d1_weighted_f1": 0.7,
                "d2_macro_f1": 0.3031,
                "d2_weighted_f1": 0.35,
                "error": "",
            }
        ]
    )


class TestCompactPrintBenchmark:
    def test_compact_output_fits_80_columns_and_shows_intervals(self, monkeypatch):
        buffer = _capture(monkeypatch)
        print_benchmark(_long_summary())
        lines = buffer.getvalue().splitlines()

        assert max(len(line) for line in lines) <= 80
        text = "\\n".join(lines)
        assert "0.378±0.08" in text
        assert "Provider" not in text and "Prompt" not in text

    def test_wide_shows_every_column(self, monkeypatch):
        buffer = _capture(monkeypatch, width=250)
        print_benchmark(_long_summary(), wide=True)
        text = buffer.getvalue()

        assert "Provider" in text and "Prompt" in text and "D1 Wt" in text

    def test_rows_without_interval_columns_still_print_plain_values(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary().drop(columns=["exact_lo", "exact_hi", "h_f1_lo", "h_f1_hi"])
        print_benchmark(df)

        assert "0.378" in buffer.getvalue() and "±" not in buffer.getvalue()

    def test_missing_scores_print_a_dash_not_nan(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary()
        df.loc[0, ["exact_match", "exact_lo", "exact_hi"]] = float("nan")
        print_benchmark(df)

        assert "nan" not in buffer.getvalue().lower()


class TestPrintContextEffect:
    def test_prints_the_paired_effect(self, monkeypatch):
        buffer = _capture(monkeypatch, width=100)
        rows = []
        for cid, none_exact, with_exact in (("c1", 0.0, 1.0), ("c2", 1.0, 1.0)):
            for mode, exact in (("none", none_exact), ("with", with_exact)):
                rows.append(
                    {
                        "config": "m", "dataset": "d", "context": mode, "case_id": cid, "text": "t", "gold": "1_1",
                        "pred": "1_1", "exact": exact, "hf1": exact, "has_context": True, "gold_d1": "1", "pred_d1": "1",
                    }
                )
        print_context_effect(pd.DataFrame(rows, columns=list(CASE_COLUMNS)))

        text = buffer.getvalue()
        assert "fixed" in text.lower() and "+0.500" in text

    def test_prints_a_note_when_nothing_is_paired(self, monkeypatch):
        buffer = _capture(monkeypatch, width=100)
        print_context_effect(pd.DataFrame(columns=list(CASE_COLUMNS)))

        assert "no cases" in buffer.getvalue().lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_eval_context.py -v`
Expected: FAIL — `TypeError: print_benchmark() got an unexpected keyword argument 'wide'` and `ImportError: cannot import name 'print_context_effect'`.

- [ ] **Step 3: Write the implementation**

In `eval.py`, add to the imports: `from rich import box` and `from .runs import ..., context_effect` (extend the Task 2 import line). Then replace `print_benchmark` with:

```python
_COMPACT_COLUMNS = (
    "config",
    "dataset",
    "context",
    "n_with_context",
    "n_cases",
    "exact_match",
    "h_f1",
    "d1_macro_f1",
    "d2_macro_f1",
    "error",
)


def _score_cell(row: pd.Series, col: str) -> str:
    """A score as ``0.378±0.08`` (value ± half-width of its interval), ``0.378`` without one, or ``—``."""
    value = row[col]
    if pd.isna(value):
        return "—"
    lo, hi = row.get(f"{col.replace('exact_match', 'exact')}_lo"), row.get(f"{col.replace('exact_match', 'exact')}_hi")
    if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
        return f"{value:.3f}"
    return f"{value:.3f}±{(hi - lo) / 2:.2f}"


def print_benchmark(df: pd.DataFrame, title: str = "Benchmark Results", wide: bool = False) -> None:
    """Render a benchmark DataFrame as a rich table.

    The default compact view keeps the columns that matter for comparing runs and fits 80 columns; scores show their
    95% bootstrap interval as ``value±half-width`` when the frame has interval columns. ``wide=True`` shows every
    column (provider, model, prompt, weighted F1). Columns absent from *df* are silently skipped.
    """
    # (key, header, style, justify, max_width, no_wrap)
    # macro_f1/micro_f1/weighted_f1 are omitted — d2_* carry the same values.
    col_spec: list[tuple[str, str, str, str, int | None, bool]] = [
        ("config", "Config", "bold cyan", "left", 22 if wide else 12, True),
        ("dataset", "Dataset", "", "left", 16 if wide else 8, True),
        ("context", "Ctx", "dim", "left", 4, True),
        ("n_with_context", "Ctx N", "dim", "right", None, False),
        ("provider", "Provider", "dim", "left", 12, True),
        ("model", "Model", "", "left", 22, True),
        ("prompt", "Prompt", "dim italic", "left", 35, True),
        ("n_cases", "N", "", "right", None, False),
        ("exact_match", "Exact", "green", "right", None, False),
        ("h_f1", "hF1", "green", "right", None, False),
        ("d1_macro_f1", "D1 Mac", "yellow", "right", None, False),
        ("d1_weighted_f1", "D1 Wt", "yellow", "right", None, False),
        ("d2_macro_f1", "D2 Mac", "magenta", "right", None, False),
        ("d2_weighted_f1", "D2 Wt", "magenta", "right", None, False),
        ("error", "Error", "bold red", "left", 30 if wide else 12, True),
    ]

    table = Table(title=title, show_lines=wide, box=box.SQUARE if wide else box.SIMPLE)
    present = [
        (col, hdr, style, just, mw, nw)
        for col, hdr, style, just, mw, nw in col_spec
        if col in df.columns and (wide or col in _COMPACT_COLUMNS)
    ]
    for _, hdr, style, just, mw, nw in present:
        justify_val = cast(Literal["left", "right", "center", "full", "default"], just)
        table.add_column(hdr, style=style or None, justify=justify_val, max_width=mw, no_wrap=nw, overflow="ellipsis")

    for _, row in df.iterrows():
        cells = []
        for col, _, _, _, _, _ in present:
            if col in ("exact_match", "h_f1"):
                cells.append(_score_cell(row, col))
            elif isinstance(row[col], float):
                cells.append("—" if pd.isna(row[col]) else f"{row[col]:.3f}")
            else:
                cells.append(str(row[col]))
        table.add_row(*cells)

    _console.print(table)
    if "context" in df.columns and (df["context"] == "with").any():
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")


def print_context_effect(cases: pd.DataFrame) -> None:
    """Print the paired none-vs-with context effect per (config, dataset) from a saved run's case rows."""
    effect = context_effect(cases)
    if effect.empty:
        _console.print("[dim]No cases carry context in both runs, so there is nothing to compare.[/dim]")
        return
    table = Table(title="Effect of context (same cases, exact match)", box=box.SIMPLE)
    for header, justify in (
        ("Config", "left"),
        ("Dataset", "left"),
        ("Paired", "right"),
        ("None", "right"),
        ("With", "right"),
        ("Δ", "right"),
        ("Fixed", "right"),
        ("Broken", "right"),
        ("Same", "right"),
    ):
        table.add_column(header, justify=cast(Literal["left", "right"], justify), no_wrap=True, overflow="ellipsis")
    for _, row in effect.iterrows():
        table.add_row(
            str(row["config"]),
            str(row["dataset"]),
            str(int(row["n_paired"])),
            f"{row['exact_none']:.3f}",
            f"{row['exact_with']:.3f}",
            f"{row['delta']:+.3f}",
            str(int(row["fixed"])),
            str(int(row["broken"])),
            str(int(row["unchanged"])),
        )
    _console.print(table)
```

Note: `_score_cell` maps `exact_match` to `exact_lo`/`exact_hi` and `h_f1` to `h_f1_lo`/`h_f1_hi`. Some long lines in the CSS f-string may trip E501 after `ruff format`; break them rather than adding a noqa.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_eval_context.py -v` then `uv run pytest tests -q`
Expected: PASS everywhere. If the 80-column assertion fails, narrow `max_width` values in the compact branch (config/dataset) until it holds; do not change the test.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg tests && uv run ruff format climafactskg tests
git add climafactskg/classifiers/cards/eval.py tests/test_eval_context.py
git commit -m "feat(eval): compact benchmark table with intervals and a context-effect view"
```

---

### Task 4: `report.py` (HTML report with inline SVG charts)

**Files:**
- Create: `climafactskg/classifiers/cards/report.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Consumes: `BenchmarkRun`, `changed_cases`, `context_effect` from Task 1; interval columns from Task 2.
- Produces: `bar_chart_svg(title, groups, series, values, lows=None, highs=None, width=720, height=260) -> str`; `render_html(runs: Sequence[BenchmarkRun], out_path) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_report.py`:

```python
"""HTML report: sections, escaping, valid inline SVG, themes, multi-run handling, failed rows."""

import re
import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from climafactskg.classifiers.cards.report import bar_chart_svg, render_html
from climafactskg.classifiers.cards.runs import CASE_COLUMNS, BenchmarkRun


def _summary_row(config="gpt", dataset="d", context="none", exact=0.4, hf1=0.6, error="", n=10, n_ctx=10):
    ok = not error
    nan = float("nan")
    return {
        "config": config, "dataset": dataset, "context": context, "n_with_context": n_ctx, "n_cases": n if ok else 0,
        "exact_match": exact if ok else nan, "exact_lo": exact - 0.1 if ok else nan, "exact_hi": exact + 0.1 if ok else nan,
        "h_f1": hf1 if ok else nan, "h_f1_lo": hf1 - 0.1 if ok else nan, "h_f1_hi": hf1 + 0.1 if ok else nan,
        "d1_macro_f1": 0.5 if ok else nan, "d2_macro_f1": 0.3 if ok else nan, "error": error,
    }


def _case(config, context, case_id, exact, pred="1_1", text="a claim"):
    return {
        "config": config, "dataset": "d", "context": context, "case_id": case_id, "text": text, "gold": "1_1",
        "pred": pred, "exact": exact, "hf1": exact, "has_context": True, "gold_d1": "1", "pred_d1": pred[0],
    }


def _run(run_id="20260929T000000Z-abc123", config="gpt", with_context=True, extra_summary=(), text="a claim"):
    summary = [_summary_row(config=config, context="none")]
    cases = [_case(config, "none", "c1", 0.0, "2_1", text), _case(config, "none", "c2", 1.0)]
    if with_context:
        summary.append(_summary_row(config=config, context="with", exact=0.6))
        cases += [_case(config, "with", "c1", 1.0, "1_1", text), _case(config, "with", "c2", 0.0, "2_1")]
    summary.extend(extra_summary)
    return BenchmarkRun(
        meta={"run_id": run_id, "created_at": "2026-09-29T00:00:00+00:00", "git_commit": "deadbeef",
              "package_version": "2.1.4", "datasets": [{"name": "d", "n_cases": 2, "n_with_context": 2}],
              "configs": [{"label": config, "provider": "p", "model": "m", "prompt": "pr"}]},
        summary=pd.DataFrame(summary),
        cases=pd.DataFrame(cases, columns=list(CASE_COLUMNS)),
    )


def _svgs(html):
    return re.findall(r"<svg.*?</svg>", html, flags=re.DOTALL)


class TestBarChartSvg:
    def test_is_well_formed_xml_with_bars_and_a_title(self):
        svg = bar_chart_svg("Exact match", ["d1", "d2"], ["a", "b"], [[0.4, 0.5], [0.6, 0.2]], [[0.3, 0.4], [0.5, 0.1]],
                            [[0.5, 0.6], [0.7, 0.3]])
        root = ET.fromstring(svg)

        assert root.tag.endswith("svg")
        assert len(root.findall(".//{*}path[@class]")) >= 4
        assert "Exact match" in svg

    def test_missing_values_are_omitted_without_error(self):
        svg = bar_chart_svg("t", ["d"], ["a", "b"], [[float("nan")], [0.5]])
        ET.fromstring(svg)
        assert "nan" not in svg.lower()

    def test_escapes_labels(self):
        svg = bar_chart_svg("<b>t</b>", ["<g>"], ["<s>"], [[0.5]])
        ET.fromstring(svg)
        assert "<b>t</b>" not in svg


class TestRenderHtml:
    def test_writes_a_self_contained_report_with_expected_sections(self, tmp_path):
        out = render_html([_run()], tmp_path / "report.html")
        html = out.read_text(encoding="utf-8")

        for heading in ("Comparison", "Context effect", "Run details"):
            assert f"<h2>{heading}</h2>" in html
        assert "claim text only" in html
        assert "prefers-color-scheme: dark" in html
        assert not re.search(r'(?:src|href)="http|@import|url\(http', html)
        assert "<script" not in html

    def test_every_svg_is_valid_xml(self, tmp_path):
        html = render_html([_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        svgs = _svgs(html)
        assert len(svgs) >= 3
        for svg in svgs:
            ET.fromstring(svg)

    def test_html_special_characters_are_escaped(self, tmp_path):
        evil = "<script>alert(1)</script> & \"quoted\""
        html = render_html([_run(config="<img src=x>", text=evil)], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "<script>alert(1)" not in html
        assert "<img src=x>" not in html
        assert "&lt;script&gt;" in html

    def test_context_sections_are_skipped_without_paired_data(self, tmp_path):
        html = render_html([_run(with_context=False)], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "<h2>Context effect</h2>" not in html
        assert "<h2>Comparison</h2>" in html

    def test_failed_combination_is_flagged_and_does_not_break_the_report(self, tmp_path):
        failed = _summary_row(config="broken", error="RuntimeError: boom")
        html = render_html([_run(extra_summary=[failed])], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "RuntimeError: boom" in html
        assert "nan" not in html.lower().replace("nanosecond", "")

    def test_identical_config_labels_across_runs_do_not_collide(self, tmp_path):
        html = render_html([_run("20260101T000000Z-aaaaaa"), _run("20260202T000000Z-bbbbbb")], tmp_path / "r.html")
        text = html.read_text(encoding="utf-8")

        assert "gpt (20260101T000)" in text and "gpt (20260202T000)" in text

    def test_creates_parent_directories_and_leaves_no_temp_file(self, tmp_path):
        out = render_html([_run()], tmp_path / "nested" / "dir" / "report.html")

        assert out.is_file()
        assert [p.name for p in out.parent.iterdir()] == ["report.html"]

    def test_requires_at_least_one_run(self, tmp_path):
        with pytest.raises(ValueError):
            render_html([], tmp_path / "r.html")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_report.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'climafactskg.classifiers.cards.report'`.

- [ ] **Step 3: Load the dataviz guidance and write the implementation**

First re-read `references/marks-and-anatomy.md` and `references/anti-patterns.md` from the dataviz skill (its base directory is printed when the skill loads) and check the chart code below against them; adjust only if the checks fail.

Create `climafactskg/classifiers/cards/report.py`:

```python
"""Self-contained HTML report for saved CARDS benchmark runs.

Plain Python string building: no jinja2, no JS, no CDN, no external URLs. Charts are inline SVG that follow the
dataviz reference palette (validated for light and dark surfaces); the comparison table is the exact-numbers view and
the relief for the light-mode slots below 3:1 contrast. Every user-supplied string is HTML-escaped.
"""

import html
import math
import os
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .runs import BenchmarkRun, changed_cases, context_effect

_SERIES_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
_SERIES_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
MAX_SERIES = len(_SERIES_LIGHT)
_METRICS = (("exact_match", "Exact match"), ("h_f1", "Hierarchical F1"), ("d2_macro_f1", "Depth-2 macro F1"))
_CI_COLUMNS = {"exact_match": ("exact_lo", "exact_hi"), "h_f1": ("h_f1_lo", "h_f1_hi")}
_esc = html.escape


def _fmt(value, digits: int = 3) -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _css() -> str:
    def variables(colors):
        return "".join(f"--s{i}:{c};" for i, c in enumerate(colors))

    light = "--surface:#fcfcfb;--text:#0b0b0b;--text2:#52514e;--grid:#dcdbd6;--rule:#e6e5e1;" + variables(_SERIES_LIGHT)
    dark = "--surface:#1a1a19;--text:#ffffff;--text2:#c3c2b7;--grid:#383835;--rule:#2b2b29;" + variables(_SERIES_DARK)
    series_rules = "".join(f".s{i}{{fill:var(--s{i})}}.k{i}{{background:var(--s{i})}}" for i in range(MAX_SERIES))
    return f"""
:root {{ color-scheme: light; {light} }}
@media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) {{ color-scheme: dark; {dark} }} }}
:root[data-theme="dark"] {{ color-scheme: dark; {dark} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 24px 16px 48px; background: var(--surface); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 980px; margin: 0 auto; }}
h1 {{ font-size: 1.5rem; margin: 0 0 4px; }} h2 {{ font-size: 1.15rem; margin: 32px 0 8px; }}
p, li, td, th, dd, dt, summary {{ color: var(--text); }} .muted {{ color: var(--text2); }}
.note {{ border-left: 3px solid var(--grid); padding: 4px 12px; color: var(--text2); margin: 12px 0; }}
.scroll {{ overflow-x: auto; }} table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
th, td {{ padding: 6px 10px; border-bottom: 1px solid var(--rule); text-align: left; white-space: nowrap; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.wrap {{ white-space: normal; min-width: 220px; }} td b {{ font-weight: 700; }} .ci {{ color: var(--text2); font-size: 0.8em; }}
.bad {{ color: var(--text); font-weight: 600; }}
.legend {{ list-style: none; display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 0; margin: 4px 0 8px; }}
.legend li {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }}
.swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
.chart {{ width: 100%; height: auto; max-width: 720px; display: block; }}
.chart text {{ fill: var(--text2); font-size: 11px; font-family: inherit; }} .chart .best {{ fill: var(--text); font-weight: 600; }}
.chart .grid {{ stroke: var(--grid); stroke-width: 1; fill: none; }} .chart .err {{ stroke: var(--text2); stroke-width: 1.5; fill: none; }}
{series_rules}
details {{ margin: 8px 0; }} dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; margin: 8px 0; }}
dt {{ color: var(--text2); }} dd {{ margin: 0; }}
"""


def bar_chart_svg(
    title: str,
    groups: Sequence[str],
    series: Sequence[str],
    values: Sequence[Sequence[float]],
    lows: Sequence[Sequence[float]] | None = None,
    highs: Sequence[Sequence[float]] | None = None,
    width: int = 720,
    height: int = 260,
) -> str:
    """A grouped bar chart as inline SVG on a fixed 0..1 axis. ``values[s][g]`` is series *s* in group *g* (NaN = none).

    Bars are at most 24px thick, rounded at the data end and square at the baseline, separated by a 2px surface gap.
    Only the best bar in each group carries a value label; every bar has a native ``<title>`` hover.
    """
    left, right, top, bottom = 40, 12, 14, 42
    plot_w, plot_h = width - left - right, height - top - bottom
    baseline = top + plot_h
    group_w = plot_w / max(len(groups), 1)
    n = max(len(series), 1)
    bar_w = max(4.0, min(24.0, (group_w - 16) / n - 2))
    cluster_w = n * bar_w + (n - 1) * 2

    def y_of(value: float) -> float:
        return top + plot_h * (1 - max(0.0, min(1.0, value)))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_esc(title)}"><title>{_esc(title)}</title>'
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1):
        y = y_of(tick)
        parts.append(f'<path class="grid" d="M{left},{y:.1f} H{width - right}"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{tick:.2f}</text>')

    for g, group in enumerate(groups):
        x0 = left + g * group_w + (group_w - cluster_w) / 2
        present = [(s, values[s][g]) for s in range(len(series)) if not math.isnan(values[s][g])]
        best = max((v for _, v in present), default=None)
        for s, value in present:
            x = x0 + s * (bar_w + 2)
            y = y_of(value)
            radius = min(4.0, baseline - y, bar_w / 2)
            interval = ""
            if lows is not None and highs is not None and not math.isnan(lows[s][g]) and not math.isnan(highs[s][g]):
                interval = f" [{lows[s][g]:.3f}–{highs[s][g]:.3f}]"
            hover = f"{series[s]} · {group}: {value:.3f}{interval}"
            if baseline - y >= 0.5:
                path = (
                    f"M{x:.1f},{baseline:.1f} V{y + radius:.1f} Q{x:.1f},{y:.1f} {x + radius:.1f},{y:.1f} "
                    f"H{x + bar_w - radius:.1f} Q{x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + radius:.1f} "
                    f"V{baseline:.1f} Z"
                )
                parts.append(f'<g><title>{_esc(hover)}</title><path class="s{s % MAX_SERIES}" d="{path}"/></g>')
            top_y = y
            if lows is not None and highs is not None and not math.isnan(lows[s][g]) and not math.isnan(highs[s][g]):
                cx, lo_y, hi_y = x + bar_w / 2, y_of(lows[s][g]), y_of(highs[s][g])
                parts.append(
                    f'<path class="err" d="M{cx:.1f},{lo_y:.1f} V{hi_y:.1f} M{cx - 3:.1f},{lo_y:.1f} H{cx + 3:.1f} '
                    f'M{cx - 3:.1f},{hi_y:.1f} H{cx + 3:.1f}"/>'
                )
                top_y = min(top_y, hi_y)
            if best is not None and value == best:
                parts.append(
                    f'<text class="best" x="{x + bar_w / 2:.1f}" y="{max(top_y - 5, 10):.1f}" '
                    f'text-anchor="middle">{value:.2f}</text>'
                )
        parts.append(
            f'<text x="{left + g * group_w + group_w / 2:.1f}" y="{height - 18}" text-anchor="middle">'
            f"{_esc(_shorten(group, 22))}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _combine(runs: Sequence[BenchmarkRun]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenates runs; with several runs the config label gets a run suffix so identical labels never collide."""
    summaries, cases = [], []
    for run in runs:
        summary, run_cases = run.summary.copy(), run.cases.copy()
        run_id = str(run.meta.get("run_id", "run"))
        if len(runs) > 1:
            suffix = f" ({run_id[:12]})"
            summary["config"] = summary["config"].astype(str) + suffix
            run_cases["config"] = run_cases["config"].astype(str) + suffix
        summary["run"], run_cases["run"] = run_id, run_id
        summaries.append(summary)
        cases.append(run_cases)
    return pd.concat(summaries, ignore_index=True), pd.concat(cases, ignore_index=True)


def _td(text: str, num: bool = False, best: bool = False, wrap: bool = False, raw: bool = False) -> str:
    body = text if raw else _esc(text)
    if best:
        body = f"<b>{body}</b>"
    css = " ".join(c for c, on in (("num", num), ("wrap", wrap)) if on)
    return f'<td class="{css}">{body}</td>' if css else f"<td>{body}</td>"


def _table(headers: Sequence[tuple[str, bool]], rows: Sequence[Sequence[str]]) -> str:
    head = "".join(f'<th class="num">{_esc(h)}</th>' if num else f"<th>{_esc(h)}</th>" for h, num in headers)
    body = "".join(f"<tr>{''.join(row)}</tr>" for row in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _comparison(summary: pd.DataFrame) -> str:
    multi = summary["run"].nunique() > 1
    best: dict[tuple[str, str], float] = {}
    for metric in ("exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"):
        if metric in summary.columns:
            for dataset, group in summary[summary["n_cases"] > 0].groupby("dataset"):
                values = group[metric].dropna()
                if not values.empty:
                    best[(str(dataset), metric)] = float(values.max())
    headers = [("Config", False), ("Dataset", False), ("Context", False), ("N", True), ("With ctx", True)]
    headers += [("Exact", True), ("hF1", True), ("D1 macro", True), ("D2 macro", True), ("Note", False)]
    rows = []
    for _, r in summary.iterrows():
        failed = bool(str(r.get("error", "")).strip())
        cells = [_td(str(r["config"])), _td(str(r["dataset"])), _td(str(r["context"])), _td(str(int(r["n_cases"])), num=True)]
        cells.append(_td(str(int(r["n_with_context"])) if "n_with_context" in r and not pd.isna(r["n_with_context"]) else "—", num=True))
        for metric in ("exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"):
            value = r.get(metric)
            is_best = not failed and (str(r["dataset"]), metric) in best and value == best[(str(r["dataset"]), metric)]
            text = _esc(_fmt(value))
            lo, hi = _CI_COLUMNS.get(metric, (None, None))
            if lo and lo in r and not failed and not pd.isna(r[lo]) and not pd.isna(r[hi]):
                text += f' <span class="ci">[{_fmt(r[lo], 2)}–{_fmt(r[hi], 2)}]</span>'
            cells.append(_td(text, num=True, best=is_best, raw=True))
        cells.append(_td(f"failed: {r['error']}" if failed else "", wrap=True))
        rows.append(cells)
    return _table(headers, rows)


def _charts(summary: pd.DataFrame) -> str:
    usable = summary[(summary["n_cases"] > 0) & summary["exact_match"].notna()]
    if usable.empty:
        return ""
    groups = list(dict.fromkeys(usable["dataset"].astype(str)))
    labels = list(
        dict.fromkeys(
            f"{c} · {'with context' if m == 'with' else 'no context'}" for c, m in zip(usable["config"], usable["context"], strict=True)
        )
    )
    dropped = max(0, len(labels) - MAX_SERIES)
    labels = labels[:MAX_SERIES]
    legend = "".join(f'<li><span class="swatch k{i}"></span>{_esc(label)}</li>' for i, label in enumerate(labels))
    out = [f'<ul class="legend">{legend}</ul>'] if len(labels) > 1 else []
    for metric, title in _METRICS:
        if metric not in usable.columns:
            continue
        nan = float("nan")
        values = [[nan] * len(groups) for _ in labels]
        lows = [[nan] * len(groups) for _ in labels]
        highs = [[nan] * len(groups) for _ in labels]
        lo_col, hi_col = _CI_COLUMNS.get(metric, (None, None))
        for _, r in usable.iterrows():
            label = f"{r['config']} · {'with context' if r['context'] == 'with' else 'no context'}"
            if label not in labels:
                continue
            s, g = labels.index(label), groups.index(str(r["dataset"]))
            values[s][g] = float(r[metric]) if not pd.isna(r[metric]) else nan
            if lo_col and lo_col in usable.columns:
                lows[s][g] = float(r[lo_col]) if not pd.isna(r[lo_col]) else nan
                highs[s][g] = float(r[hi_col]) if not pd.isna(r[hi_col]) else nan
        out.append(f"<h3>{_esc(title)}</h3>")
        out.append(bar_chart_svg(title, groups, labels, values, lows if lo_col else None, highs if lo_col else None))
    if dropped:
        out.append(f'<p class="note">{dropped} further series are not drawn; see the comparison table.</p>')
    return "".join(out)


def _context_sections(cases: pd.DataFrame) -> str:
    effect = context_effect(cases)
    if effect.empty:
        return ""
    headers = [("Config", False), ("Dataset", False), ("Paired", True), ("None", True), ("With", True), ("Δ", True)]
    headers += [("Fixed", True), ("Broken", True), ("Same", True)]
    rows = [
        [
            _td(str(r["config"])), _td(str(r["dataset"])), _td(str(int(r["n_paired"])), num=True),
            _td(_fmt(r["exact_none"]), num=True), _td(_fmt(r["exact_with"]), num=True), _td(f"{r['delta']:+.3f}", num=True),
            _td(str(int(r["fixed"])), num=True), _td(str(int(r["broken"])), num=True), _td(str(int(r["unchanged"])), num=True),
        ]
        for _, r in effect.iterrows()
    ]
    out = [
        "<h2>Context effect</h2>",
        '<p class="muted">Exact match without and with context on the same cases (only cases that carry context). '
        "Fixed: wrong without, right with; broken: the reverse.</p>",
        _table(headers, rows),
    ]
    changed = changed_cases(cases, limit=20)
    if not changed.empty:
        out.append("<h3>Cases changed by context</h3>")
        change_rows = [
            [
                _td(str(r["config"])), _td(str(r["change"])), _td(_shorten(r["text"], 160), wrap=True),
                _td(str(r["gold"])), _td(str(r["pred_none"])), _td(str(r["pred_with"])),
            ]
            for _, r in changed.iterrows()
        ]
        out.append(
            _table(
                [("Config", False), ("Change", False), ("Claim", False), ("Gold", False), ("No context", False), ("With context", False)],
                change_rows,
            )
        )
    return "".join(out)


def _details(runs: Sequence[BenchmarkRun]) -> str:
    out = ["<h2>Run details</h2>"]
    for run in runs:
        meta = run.meta
        pairs = [
            ("Run", meta.get("run_id")), ("Created", meta.get("created_at")), ("Commit", meta.get("git_commit")),
            ("Package version", meta.get("package_version")), ("Context modes", ", ".join(meta.get("context_modes", []))),
            ("Datasets", "; ".join(f"{d['name']} ({d['n_cases']} cases, {d['n_with_context']} with context)" for d in meta.get("datasets", []))),
            ("Configs", "; ".join(f"{c['label']} = {c.get('model', '')} via {c.get('provider', '')}" for c in meta.get("configs", []))),
        ]
        items = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(str(v)) if v not in (None, '') else '—'}</dd>" for k, v in pairs)
        out.append(f"<details open><summary>{_esc(str(meta.get('run_id', 'run')))}</summary><dl>{items}</dl></details>")
    return "".join(out)


def render_html(runs: Sequence[BenchmarkRun], out_path: str | Path) -> Path:
    """Renders *runs* as one self-contained HTML report at *out_path* and returns the path."""
    if not runs:
        raise ValueError("render_html needs at least one run")
    summary, cases = _combine(runs)
    if "error" not in summary.columns:
        summary["error"] = ""
    summary["error"] = summary["error"].fillna("")
    caveat = ""
    if (summary["context"] == "with").any():
        caveat = (
            '<p class="note">Gold labels were annotated from claim text only, so with-context scores measure agreement '
            "with claim-only labels, not accuracy against a context-informed truth. Intervals are 95% bootstrap over "
            "cases; differences inside them are noise.</p>"
        )
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>CARDS evaluation report</title>'
        f"<style>{_css()}</style></head><body><main><h1>CARDS evaluation report</h1>"
        f'<p class="muted">{len(runs)} run(s), {len(summary)} result row(s).</p>{caveat}'
        f"<h2>Comparison</h2>{_comparison(summary)}<h2>Charts</h2>{_charts(summary)}"
        f"{_context_sections(cases)}{_details(runs)}</main></body></html>"
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_text(document, encoding="utf-8")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_report.py -v` then `uv run pytest tests -q`
Expected: PASS. If a chart-related test fails, fix the code, not the assertion. Then open one generated report in a browser (or render it and read the HTML) and check light and dark: labels do not collide, nothing overflows at phone width, bars have gaps and rounded tops.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg tests && uv run ruff format climafactskg tests
git add climafactskg/classifiers/cards/report.py tests/test_report.py
git commit -m "feat(eval): add a self-contained HTML report with inline SVG charts"
```

---

### Task 5: `eval-report` command, docs and a real render

**Files:**
- Modify: `climafactskg/cli.py`
- Create: `tests/test_cli_eval_report.py`
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-09-29-eval-reporting-design.md`

**Interfaces:**
- Consumes: `load_run`, `render_html`.
- Produces: `climafactskg eval-report RUN_DIR [RUN_DIR ...] [--out PATH]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_eval_report.py`:

```python
"""Tests for climafactskg.cli's `eval-report` command."""

import pandas as pd
from climafactskg.classifiers.cards.runs import CASE_COLUMNS, BenchmarkRun, save_run
from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _saved_run(base):
    summary = pd.DataFrame(
        [{"config": "m", "dataset": "d", "context": "none", "n_with_context": 0, "n_cases": 2, "exact_match": 0.5,
          "h_f1": 0.6, "d1_macro_f1": 0.5, "d2_macro_f1": 0.3, "error": ""}]
    )
    cases = pd.DataFrame(
        [{"config": "m", "dataset": "d", "context": "none", "case_id": "c1", "text": "t", "gold": "1_1", "pred": "1_1",
          "exact": 1.0, "hf1": 1.0, "has_context": False, "gold_d1": "1", "pred_d1": "1"}],
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_eval_report.py -v`
Expected: FAIL — exit code 2 (no such command).

- [ ] **Step 3: Write the implementation**

In `climafactskg/cli.py`, add after the `eval_context` command:

```python
@app.command(name="eval-report")
def eval_report(
    run_dirs: list[str] = typer.Argument(..., help="One or more saved benchmark run directories (data/eval_runs/...)."),
    out: Optional[str] = typer.Option(None, "--out", help="Report path. Defaults to <first run dir>/report.html."),
):
    """Render saved benchmark runs as one self-contained HTML report (tables and inline SVG charts)."""
    from climafactskg.classifiers.cards.report import render_html
    from climafactskg.classifiers.cards.runs import load_run

    try:
        runs = [load_run(path) for path in run_dirs]
    except ValueError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc
    target = out or f"{run_dirs[0].rstrip('/')}/report.html"
    logger.info("Wrote %s", render_html(runs, target))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_eval_report.py -v` then `uv run pytest tests -q`
Expected: PASS.

- [ ] **Step 5: Docs**

- `CLAUDE.md` (Commands block): add `climafactskg eval-report data/eval_runs/<run> [<run> ...] [--out report.html]   # HTML report from saved benchmark runs`. In the eval bullet add: `benchmark_configs(..., save_dir="data/eval_runs")` saves each run (`run.json`, tidy `cases.csv`, `summary.csv`) and attaches `df.attrs["run_dir"]`; the summary carries 95% bootstrap intervals (`exact_lo/hi`, `h_f1_lo/hi`); `print_benchmark` is compact by default (`wide=True` for everything) and prints `value±half-width`; `print_context_effect(cases)` shows the paired none-vs-with effect; `eval-report` renders one or more saved runs to a self-contained HTML file (inline SVG, no JS/CDN, no new dependency). Update the test count to the total from `uv run pytest tests -q` and add `runs.py`/`report.py` to the covered list.
- Spec: append a "Deviations while planning" section listing the three deviations from this plan's header (loop kept in place instead of `_run_combo`; compact table shows `value±half-width`; report built with plain strings, not jinja2).

- [ ] **Step 6: Full checks and a real render**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest tests -q
```
Expected: clean; all tests pass.

Real render from the warm cache, no paid calls (skip if the cache file is gone; the fixture tests already cover rendering). Use the session scratchpad cache from the earlier tuning runs (`.../scratchpad/tune_cache.db`, `openai/gpt-4o-mini` via OpenRouter, budget 800):

```bash
uv run python - <<'EOF'
import glob
from climafactskg.classifiers.cards import CARDSLLMClassifier
from climafactskg.classifiers.cards.eval import benchmark_configs, climatesense_dataset_v2, print_benchmark, print_context_effect
from climafactskg.classifiers.cards.runs import load_run

caches = glob.glob("/private/tmp/claude-*/**/scratchpad/tune_cache.db", recursive=True)
assert caches, "warm cache not found; skip this step"
clf = CARDSLLMClassifier(provider="openrouter", model="openai/gpt-4o-mini", use_preclassifier=False, cache_path=caches[0])
ds = climatesense_dataset_v2(with_context=True, max_context_chars=800)
df = benchmark_configs({"gpt-4o-mini": clf}, {"cs_v2": ds}, save_dir="data/eval_runs")
print_benchmark(df)
print_context_effect(load_run(df.attrs["run_dir"]).cases)
print(df.attrs["run_dir"])
EOF
uv run climafactskg eval-report data/eval_runs/<the printed run dir>
```
Expected: two rows (`none`, `with`) matching the earlier sweep (exact 0.378 and 0.301, hF1 0.608 and 0.580), a context-effect table, and `report.html` beside the run. If any case was not cached the classifier will make a few paid calls: check `https://openrouter.ai/api/v1/key` first (the key had about $3 left) and stop instead of spending. Open the HTML and check light and dark.

- [ ] **Step 7: Commit**

```bash
git add climafactskg/cli.py tests/test_cli_eval_report.py CLAUDE.md docs/superpowers/specs/2026-09-29-eval-reporting-design.md
git commit -m "feat(cli): add eval-report and document saved runs"
```

(Do not commit anything under `data/eval_runs/`; it is git-ignored.)
