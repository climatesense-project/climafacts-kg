"""Saved CARDS benchmark runs: persistence, bootstrap intervals and paired context analysis."""

import json
import logging
import math
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
_EFFECT_COLUMNS = (
    "config",
    "dataset",
    "n_paired",
    "exact_none",
    "exact_with",
    "delta",
    "delta_lo",
    "delta_hi",
    "fixed",
    "broken",
    "unchanged",
    "p_value",
)
_COMPARISON_COLUMNS = (
    "dataset",
    "config",
    "baseline",
    "n_paired",
    "exact_baseline",
    "exact_config",
    "delta",
    "delta_lo",
    "delta_hi",
    "better",
    "worse",
    "unchanged",
    "p_value",
)
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
    # Everything is read as text so empty claims and labels such as "None"/"NA" stay strings; scores become numbers.
    cases = pd.read_csv(directory / "cases.csv", dtype=str, keep_default_na=False)
    missing = [c for c in CASE_COLUMNS if c not in cases.columns]
    if missing:
        raise ValueError(f"{directory}/cases.csv: missing columns {missing}")
    for column in ("exact", "hf1"):
        cases[column] = pd.to_numeric(cases[column], errors="coerce")
    cases["has_context"] = cases["has_context"].map(lambda value: str(value) == "True").astype(bool)
    summary = pd.read_csv(
        directory / "summary.csv",
        dtype={"config": str, "dataset": str, "context": str},
        keep_default_na=False,
        na_values=[""],
    )
    missing = [c for c in _SUMMARY_REQUIRED if c not in summary.columns]
    if missing:
        raise ValueError(f"{directory}/summary.csv: missing columns {missing}")
    if "error" in summary.columns:
        summary["error"] = summary["error"].fillna("")
    return BenchmarkRun(meta=meta, summary=summary, cases=cases, path=directory)


def _paired(cases: pd.DataFrame) -> pd.DataFrame:
    """Rows with the exact score without and with context for the same (config, dataset, case) that has context."""
    covered = cases[cases["has_context"].astype(bool)]
    key = ["config", "dataset", "case_id"]
    none = covered[covered["context"] == "none"][[*key, "exact", "pred", "text", "gold"]]
    with_ = covered[covered["context"] == "with"][[*key, "exact", "pred"]]
    paired = none.merge(with_, on=key, suffixes=("_none", "_with")).dropna(subset=["exact_none", "exact_with"])
    paired["fixed"] = (paired["exact_none"] < 1) & (paired["exact_with"] >= 1)
    paired["broken"] = (paired["exact_none"] >= 1) & (paired["exact_with"] < 1)
    return paired


def mcnemar_exact(better: int, worse: int) -> float:
    """Exact two-sided McNemar p-value for paired outcomes.

    *better* and *worse* are the discordant pairs (right only on one side / right only on the other); concordant
    pairs carry no information. Under "no difference" each discordant pair is equally likely to go either way, so the
    p-value is twice the binomial tail P(X <= min(better, worse)) with n = better + worse, capped at 1.
    """
    n = better + worse
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(better, worse) + 1))
    return min(1.0, 2 * tail / 2**n)


def _summarize_pairs(paired: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Per-group paired statistics from rows with ``exact_left`` / ``exact_right`` (the exact score on each side).

    ``better``: wrong on the left, right on the right; ``worse``: the reverse. ``delta`` is right minus left, with a
    deterministic 95% bootstrap interval over the pairs and the exact McNemar p-value.
    """
    rows = []
    for key, rows_of_group in paired.groupby(group, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        left, right = rows_of_group["exact_left"], rows_of_group["exact_right"]
        better = int(((left < 1) & (right >= 1)).sum())
        worse = int(((left >= 1) & (right < 1)).sum())
        delta_lo, delta_hi = bootstrap_ci((right - left).to_numpy())
        rows.append(
            {
                **dict(zip(group, key, strict=True)),
                "n_paired": len(rows_of_group),
                "exact_left": round(float(left.mean()), 4),
                "exact_right": round(float(right.mean()), 4),
                "delta": round(float(right.mean() - left.mean()), 4),
                "delta_lo": round(delta_lo, 4),
                "delta_hi": round(delta_hi, 4),
                "better": better,
                "worse": worse,
                "unchanged": len(rows_of_group) - better - worse,
                "p_value": mcnemar_exact(better, worse),
            }
        )
    return pd.DataFrame(rows)


def context_effect(cases: pd.DataFrame) -> pd.DataFrame:
    """Paired effect of context per (config, dataset), on the cases that actually have context.

    ``fixed``: wrong without context, right with it; ``broken``: the reverse. ``delta`` (with minus without) comes
    with a 95% bootstrap interval over the pairs and the exact McNemar p-value (``p_value``). Empty when nothing is
    paired.
    """
    paired = _paired(cases)
    if paired.empty:
        return pd.DataFrame(columns=list(_EFFECT_COLUMNS))
    summary = _summarize_pairs(
        paired.rename(columns={"exact_none": "exact_left", "exact_with": "exact_right"}), ["config", "dataset"]
    ).rename(columns={"exact_left": "exact_none", "exact_right": "exact_with", "better": "fixed", "worse": "broken"})
    return summary[list(_EFFECT_COLUMNS)]


def compare_configs(cases: pd.DataFrame, baseline: str, context: str = "none") -> pd.DataFrame:
    """Compares every other config with *baseline* on the cases both answered, per dataset.

    Pairs are matched on ``(dataset, case_id)`` within one context mode. ``better``: the config is right where the
    baseline is wrong; ``worse``: the reverse. Each row carries ``delta`` (config minus baseline), its 95% bootstrap
    interval and the exact McNemar ``p_value``. The p-values are not corrected for the number of comparisons.

    Raises:
        ValueError: if *baseline* has no rows in that context mode.
    """
    in_mode = cases[cases["context"] == context]
    base = in_mode[in_mode["config"] == baseline]
    if base.empty:
        raise ValueError(f"no rows for baseline config {baseline!r} in context mode {context!r}")
    others = in_mode[in_mode["config"] != baseline]
    paired = (
        base[["dataset", "case_id", "exact"]]
        .rename(columns={"exact": "exact_left"})
        .merge(
            others[["config", "dataset", "case_id", "exact"]].rename(columns={"exact": "exact_right"}),
            on=["dataset", "case_id"],
        )
        .dropna(subset=["exact_left", "exact_right"])
    )
    if paired.empty:
        return pd.DataFrame(columns=list(_COMPARISON_COLUMNS))
    summary = _summarize_pairs(paired, ["dataset", "config"]).rename(
        columns={"exact_left": "exact_baseline", "exact_right": "exact_config"}
    )
    summary["baseline"] = baseline
    return summary[list(_COMPARISON_COLUMNS)]


def changed_cases(cases: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    """Cases whose exact-match outcome flipped with context (``change`` is ``fixed`` or ``broken``).

    At most *limit* rows per (config, dataset), so one busy config cannot crowd out the others.
    """
    paired = _paired(cases)
    changed = paired[paired["fixed"] | paired["broken"]].copy()
    if changed.empty:
        return pd.DataFrame(columns=list(_CHANGED_COLUMNS))
    changed["change"] = np.where(changed["fixed"], "fixed", "broken")
    changed = changed.groupby(["config", "dataset"], sort=False).head(limit)
    return changed[list(_CHANGED_COLUMNS)].reset_index(drop=True)


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
    category_scores: str = "all",
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
        "category_scores": category_scores,
    }
