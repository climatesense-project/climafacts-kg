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
td.wrap {{ white-space: normal; min-width: 220px; }}
td b {{ font-weight: 700; }}
.ci {{ color: var(--text2); font-size: 0.8em; }}
.bad {{ color: var(--text); font-weight: 600; }}
.legend {{ list-style: none; display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 0; margin: 4px 0 8px; }}
.legend li {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }}
.swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
.chart {{ width: 100%; height: auto; max-width: 720px; display: block; }}
.chart text {{ fill: var(--text2); font-size: 11px; font-family: inherit; }}
.chart .best {{ fill: var(--text); font-weight: 600; }}
.chart .grid {{ stroke: var(--grid); stroke-width: 1; fill: none; }}
.chart .err {{ stroke: var(--text2); stroke-width: 1.5; fill: none; }}
{series_rules}
details {{ margin: 8px 0; }}
dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; margin: 8px 0; }}
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
        labelled = False  # one value label per group, even when several bars tie for best
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
            if best is not None and value == best and not labelled:
                labelled = True
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
    ids = [str(run.meta.get("run_id", "run")) for run in runs]
    if len(set(ids)) < len(ids):  # missing or repeated ids: fall back to the position so labels stay distinct
        ids = [f"{run_id}#{i + 1}" for i, run_id in enumerate(ids)]
    for run, run_id in zip(runs, ids, strict=True):
        summary, run_cases = run.summary.copy(), run.cases.copy()
        if len(runs) > 1:
            suffix = f" ({run_id})"
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
        failed = bool(str(r.get("error", "")).strip()) or int(r["n_cases"]) == 0  # nothing evaluated: show dashes
        cells = [
            _td(str(r["config"])),
            _td(str(r["dataset"])),
            _td(str(r["context"])),
            _td(str(int(r["n_cases"])), num=True),
        ]
        cells.append(
            _td(
                str(int(r["n_with_context"])) if "n_with_context" in r and not pd.isna(r["n_with_context"]) else "—",
                num=True,
            )
        )
        for metric in ("exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"):
            value = r.get(metric)
            is_best = not failed and (str(r["dataset"]), metric) in best and value == best[(str(r["dataset"]), metric)]
            text = "—" if failed else _esc(_fmt(value))
            lo, hi = _CI_COLUMNS.get(metric, (None, None))
            if lo and lo in r and not failed and not pd.isna(r[lo]) and not pd.isna(r[hi]):
                text += f' <span class="ci">[{_fmt(r[lo], 2)}–{_fmt(r[hi], 2)}]</span>'
            cells.append(_td(text, num=True, best=is_best, raw=True))
        error = str(r.get("error", "")).strip()
        cells.append(_td(f"failed: {error}" if error else ("no cases evaluated" if failed else ""), wrap=True))
        rows.append(cells)
    return _table(headers, rows)


def _charts(summary: pd.DataFrame) -> str:
    usable = summary[(summary["n_cases"] > 0) & summary["exact_match"].notna()]
    if usable.empty:
        return ""
    groups = list(dict.fromkeys(usable["dataset"].astype(str)))
    labels = list(
        dict.fromkeys(
            f"{c} · {'with context' if m == 'with' else 'no context'}"
            for c, m in zip(usable["config"], usable["context"], strict=True)
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
            _td(str(r["config"])),
            _td(str(r["dataset"])),
            _td(str(int(r["n_paired"])), num=True),
            _td(_fmt(r["exact_none"]), num=True),
            _td(_fmt(r["exact_with"]), num=True),
            _td(f"{r['delta']:+.3f}", num=True),
            _td(str(int(r["fixed"])), num=True),
            _td(str(int(r["broken"])), num=True),
            _td(str(int(r["unchanged"])), num=True),
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
                _td(str(r["config"])),
                _td(str(r["dataset"])),
                _td(str(r["change"])),
                _td(_shorten(r["text"], 160), wrap=True),
                _td(str(r["gold"])),
                _td(str(r["pred_none"])),
                _td(str(r["pred_with"])),
            ]
            for _, r in changed.iterrows()
        ]
        out.append(
            _table(
                [
                    ("Config", False),
                    ("Dataset", False),
                    ("Change", False),
                    ("Claim", False),
                    ("Gold", False),
                    ("No context", False),
                    ("With context", False),
                ],
                change_rows,
            )
        )
    return "".join(out)


def _details(runs: Sequence[BenchmarkRun]) -> str:
    out = ["<h2>Run details</h2>"]
    for run in runs:
        meta = run.meta
        pairs = [
            ("Run", meta.get("run_id")),
            ("Created", meta.get("created_at")),
            ("Commit", meta.get("git_commit")),
            ("Package version", meta.get("package_version")),
            ("Context modes", ", ".join(meta.get("context_modes", []))),
            (
                "Datasets",
                "; ".join(
                    f"{d['name']} ({d['n_cases']} cases, {d['n_with_context']} with context)"
                    for d in meta.get("datasets", [])
                ),
            ),
            (
                "Configs",
                "; ".join(
                    f"{c['label']} = {c.get('model', '')} via {c.get('provider', '')}" for c in meta.get("configs", [])
                ),
            ),
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
