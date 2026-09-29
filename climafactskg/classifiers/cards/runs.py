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


def bootstrap_ci(
    values: Iterable[float], n_boot: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float]:
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
    _write_atomic(
        target / "run.json", lambda p: p.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    )
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
