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

from .runs import BenchmarkRun, changed_cases, compare_configs, context_effect

_SERIES_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
_SERIES_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
MAX_SERIES = len(_SERIES_LIGHT)
_METRICS = (("exact_match", "Exact match"), ("h_f1", "Hierarchical F1"), ("d2_macro_f1", "Depth-2 macro F1"))
_CI_COLUMNS = {
    "exact_match": ("exact_lo", "exact_hi"),
    "h_f1": ("h_f1_lo", "h_f1_hi"),
    "d2_macro_f1": ("d2_macro_f1_lo", "d2_macro_f1_hi"),
}
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
main {{ max-width: 1240px; margin: 0 auto; }}
h1 {{ font-size: 1.5rem; margin: 0 0 4px; }} h2 {{ font-size: 1.15rem; margin: 32px 0 8px; }}
p, li, td, th, dd, dt, summary {{ color: var(--text); }} .muted {{ color: var(--text2); }}
.note {{ border-left: 3px solid var(--grid); padding: 4px 12px; color: var(--text2); margin: 12px 0; }}
.scroll {{ overflow-x: auto; }} table {{ border-collapse: collapse; width: 100%; font-size: 0.86rem; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--rule); text-align: left; white-space: nowrap; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.wrap {{ white-space: normal; min-width: 150px; }}
td b {{ font-weight: 700; }}
.ci {{ color: var(--text2); font-size: 0.8em; }}
.bad {{ color: var(--text); font-weight: 600; }}
.legend {{ list-style: none; display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 0; margin: 4px 0 8px; }}
.legend li {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }}
.swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
.chart {{ width: 100%; height: auto; max-width: 720px; display: block; }}
.chart.wide {{ max-width: 960px; }}
.chart text {{ fill: var(--text2); font-size: 11px; font-family: inherit; }}
.chart .best {{ fill: var(--text); font-weight: 600; }}
.chart .grid {{ stroke: var(--grid); stroke-width: 1; fill: none; }}
.chart .err {{ stroke: var(--text2); stroke-width: 1.5; fill: none; }}
.chart text.lbl {{ paint-order: stroke; stroke: var(--surface); stroke-width: 3px; stroke-linejoin: round; }}
.chart .frontier {{ stroke: var(--text2); stroke-width: 1.5; stroke-dasharray: 4 3; fill: none; }}
.chart .dot {{ fill: var(--s0); stroke: var(--surface); stroke-width: 2; }}
.chart .dot.hollow {{ fill: var(--surface); stroke: var(--s0); }}
{series_rules}
details {{ margin: 8px 0; }}
h4 {{ font-size: 0.98rem; margin: 20px 0 6px; }}
section.benchmark {{ margin-top: 44px; padding-top: 4px; border-top: 2px solid var(--rule); }}
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


def ranked_bars_svg(title: str, items: Sequence[tuple[str, float, float, float]], width: int = 720) -> str:
    """Horizontal bars, best first, for many models: ``items`` are ``(label, value, lo, hi)`` on a fixed 0..1 axis."""
    ordered = sorted(items, key=lambda item: -item[1])
    left, right, top, row = 200, 56, 8, 22
    plot_w = width - left - right
    height = top + row * len(ordered) + 30
    baseline = top + row * len(ordered)

    def x_of(value: float) -> float:
        return left + plot_w * max(0.0, min(1.0, value))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_esc(title)}"><title>{_esc(title)}</title>'
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1):
        x = x_of(tick)
        parts.append(f'<path class="grid" d="M{x:.1f},{top} V{baseline}"/>')
        parts.append(f'<text x="{x:.1f}" y="{baseline + 16}" text-anchor="middle">{tick:.2f}</text>')
    for n, (label, value, lo, hi) in enumerate(ordered):
        y = top + n * row
        mid = y + row / 2
        interval = "" if math.isnan(lo) or math.isnan(hi) else f" [{lo:.3f}–{hi:.3f}]"
        parts.append(f'<text x="{left - 8}" y="{mid + 4:.1f}" text-anchor="end">{_esc(_shorten(label, 30))}</text>')
        parts.append(
            f"<g><title>{_esc(f'{label}: {value:.3f}{interval}')}</title>"
            f'<rect class="s0" x="{left}" y="{y + 3}" width="{max(x_of(value) - left, 0.5):.1f}" '
            f'height="{row - 8}" rx="3"/></g>'
        )
        if not (math.isnan(lo) or math.isnan(hi)):
            parts.append(
                f'<path class="err" d="M{x_of(lo):.1f},{mid:.1f} H{x_of(hi):.1f} M{x_of(lo):.1f},{mid - 3:.1f} '
                f'V{mid + 3:.1f} M{x_of(hi):.1f},{mid - 3:.1f} V{mid + 3:.1f}"/>'
            )
        end = x_of(hi if not math.isnan(hi) else value)
        parts.append(f'<text x="{end + 6:.1f}" y="{mid + 4:.1f}">{value:.2f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _pareto_front(points: Sequence[tuple[float, float]]) -> list[int]:
    """Indexes of the ``(size, value)`` points that no smaller-or-equal-size point beats: the efficient frontier."""
    kept: list[int] = []
    best = -math.inf
    for index in sorted(range(len(points)), key=lambda i: (points[i][0], -points[i][1])):
        if points[index][1] > best:
            kept.append(index)
            best = points[index][1]
    return kept


def _fmt_size(size: float, active: float | None = None) -> str:
    text = f"{size:g}B"
    return f"{text} ({active:g}B active)" if active else text


def size_scatter_svg(title: str, points: Sequence[dict], width: int = 900, height: int = 420) -> str:
    """Result against model size as inline SVG: log x axis, 95% interval whiskers and the efficient frontier.

    *points* are dicts with ``label``, ``size`` (billions of parameters), ``active`` (or ``None``), ``value`` (0..1),
    ``lo``/``hi`` (NaN for no interval) and ``flag`` (a hollow marker: the score understates the model).
    """
    left, right, top, bottom = 44, 24, 18, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    sizes = [p["size"] for p in points]
    # The axis hugs the data (a little padding either side) so points are not squeezed into one corner.
    lo_log = math.log10(min(sizes)) - 0.2
    hi_log = math.log10(max(sizes)) + 0.2
    if hi_log - lo_log < 0.8:
        lo_log, hi_log = lo_log - 0.4, hi_log + 0.4

    def x_of(size: float) -> float:
        return left + plot_w * (math.log10(size) - lo_log) / (hi_log - lo_log)

    def y_of(value: float) -> float:
        return top + plot_h * (1 - max(0.0, min(1.0, value)))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="chart wide" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_esc(title)}"><title>{_esc(title)}</title>'
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1):
        y = y_of(tick)
        parts.append(f'<path class="grid" d="M{left},{y:.1f} H{width - right}"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{tick:.2f}</text>')
    for exp in range(math.floor(lo_log), math.ceil(hi_log) + 1):
        for step in (1, 3):  # 1, 3, 10, 30, 100, 300 ...
            tick_size = step * 10.0**exp
            if lo_log <= math.log10(tick_size) <= hi_log:
                x = x_of(tick_size)
                parts.append(f'<path class="grid" d="M{x:.1f},{top} V{top + plot_h}"/>')
                parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle">{tick_size:g}B</text>')
    parts.append(
        f'<text x="{left + plot_w / 2:.1f}" y="{height - 6}" text-anchor="middle">'
        "Model size (parameters, log scale)</text>"
    )

    front = _pareto_front([(p["size"], p["value"]) for p in points])
    if len(front) > 1:
        path = " ".join(
            f"{'M' if n == 0 else 'L'}{x_of(points[i]['size']):.1f},{y_of(points[i]['value']):.1f}"
            for n, i in enumerate(front)
        )
        parts.append(f'<path class="frontier" d="{path}"/>')

    # Boxes a label must not cover: every dot and whisker, then the labels already placed (x0, x1, y0, y1).
    placed: list[tuple[float, float, float, float]] = []
    for q in points:
        qx, qy = x_of(q["size"]), y_of(q["value"])
        placed.append((qx - 7, qx + 7, qy - 7, qy + 7))
        if not (math.isnan(q["lo"]) or math.isnan(q["hi"])):
            placed.append((qx - 3, qx + 3, y_of(q["hi"]), y_of(q["lo"])))
    for p in sorted(points, key=lambda q: q["size"]):
        cx, cy = x_of(p["size"]), y_of(p["value"])
        has_interval = not (math.isnan(p["lo"]) or math.isnan(p["hi"]))
        if has_interval:
            lo_y, hi_y = y_of(p["lo"]), y_of(p["hi"])
            parts.append(
                f'<path class="err" d="M{cx:.1f},{lo_y:.1f} V{hi_y:.1f} M{cx - 3:.1f},{lo_y:.1f} H{cx + 3:.1f} '
                f'M{cx - 3:.1f},{hi_y:.1f} H{cx + 3:.1f}"/>'
            )
        hover = f"{p['label']} · {_fmt_size(p['size'], p['active'])} · {p['value']:.3f}"
        if has_interval:
            hover += f" [{p['lo']:.3f}–{p['hi']:.3f}]"
        if p["flag"]:
            hover += " · failed on more than 10% of claims"
        css = "dot hollow" if p["flag"] else "dot"
        parts.append(f'<g><title>{_esc(hover)}</title><circle class="{css}" cx="{cx:.1f}" cy="{cy:.1f}" r="5"/></g>')

        label = _shorten(str(p["label"]), 26)
        text_w = 6.2 * len(label)
        for dx, dy, anchor in (
            (8, 4, "start"),
            (8, -10, "start"),
            (8, 18, "start"),
            (-8, 4, "end"),
            (-8, -10, "end"),
            (-8, 18, "end"),
            (8, -24, "start"),
            (8, 32, "start"),
        ):
            x0 = cx + dx if anchor == "start" else cx + dx - text_w
            box = (x0, x0 + text_w, cy + dy - 10, cy + dy + 3)
            fits = left <= box[0] and box[1] <= width - right
            if fits and not any(box[0] < b[1] and b[0] < box[1] and box[2] < b[3] and b[2] < box[3] for b in placed):
                break
        else:
            dx, dy, anchor = 8, 4, "start"
            x0 = cx + dx
            box = (x0, x0 + text_w, cy + dy - 10, cy + dy + 3)
        placed.append(box)
        parts.append(
            f'<text class="lbl" x="{cx + dx:.1f}" y="{cy + dy:.1f}" text-anchor="{anchor}">{_esc(label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _size_section(summary: pd.DataFrame) -> str:
    """Result against model size per dataset; empty unless at least two configs of a dataset have a known size."""
    if "size_b" not in summary.columns:
        return ""
    usable = summary[(summary["n_cases"] > 0) & summary["exact_match"].notna()]
    blocks: list[str] = []
    for dataset in dict.fromkeys(usable["dataset"].astype(str)):
        group = usable[usable["dataset"].astype(str) == dataset]
        mixed = _has_not_climate(group) and "exact_category" in group.columns and group["exact_category"].notna().any()
        metric = "exact_category" if mixed else "exact_match"
        points: list[dict] = []
        unsized: list[str] = []
        for config in dict.fromkeys(group["config"].astype(str)):
            rows = group[group["config"].astype(str) == config]
            row = rows[rows["context"] == "none"].iloc[0] if (rows["context"] == "none").any() else rows.iloc[0]
            if pd.isna(row["size_b"]) or pd.isna(row[metric]):
                unsized.append(config)
                continue
            n_failed = 0 if pd.isna(row.get("n_failed")) else float(row["n_failed"])
            has_interval = (
                metric == "exact_match" and not pd.isna(row.get("exact_lo")) and not pd.isna(row.get("exact_hi"))
            )
            points.append(
                {
                    "label": config,
                    "size": float(row["size_b"]),
                    "active": None if pd.isna(row.get("active_b")) else float(row["active_b"]),
                    "value": float(row[metric]),
                    "lo": float(row["exact_lo"]) if has_interval else float("nan"),
                    "hi": float(row["exact_hi"]) if has_interval else float("nan"),
                    "flag": n_failed / max(float(row["n_cases"]), 1) > 0.10,
                }
            )
        if len(points) < 2:
            continue
        title = f"{dataset}: {'exact match on cases with a category' if mixed else 'exact match'} against model size"
        block = f"<h3>{_esc(dataset)}</h3>" + size_scatter_svg(title, points)
        notes = ["Dashed line: models that no smaller model beats."]
        if any(p["flag"] for p in points):
            notes.append("Hollow marker: failed on more than 10% of claims, so its score understates the model.")
        if unsized:
            notes.append(
                f"No published size, so not plotted: {', '.join(_esc(name) for name in unsized)} "
                "(state `size_b` for them in the config)."
            )
        blocks.append(block + f'<p class="muted">{" ".join(notes)}</p>')
    return "<h2>Size and result</h2>" + "".join(blocks) if blocks else ""


def _combine(runs: Sequence[BenchmarkRun]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenates runs; with several runs the config label gets a run suffix so identical labels never collide."""
    summaries, cases = [], []
    ids = [str(run.meta.get("run_id", "run")) for run in runs]
    if len(set(ids)) < len(ids):  # missing or repeated ids: fall back to the position so labels stay distinct
        ids = [f"{run_id}#{i + 1}" for i, run_id in enumerate(ids)]
    for run, run_id in zip(runs, ids, strict=True):
        summary, run_cases = run.summary.copy(), run.cases.copy()
        sizes = {str(c.get("label")): (c.get("size_b"), c.get("active_b")) for c in run.meta.get("configs", [])}
        summary["size_b"] = [sizes.get(str(c), (None, None))[0] for c in summary["config"]]
        summary["active_b"] = [sizes.get(str(c), (None, None))[1] for c in summary["config"]]
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


def _count(value) -> str:
    """An integer count, or a dash when it is missing (older saved runs do not have every column)."""
    return "—" if value is None or pd.isna(value) else str(int(value))


def _has_not_climate(summary: pd.DataFrame) -> bool:
    return "n_not_climate" in summary.columns and bool((summary["n_not_climate"].fillna(0) > 0).any())


def _comparison(summary: pd.DataFrame) -> str:
    show_category = _has_not_climate(summary) and "exact_category" in summary.columns
    best: dict[tuple[str, str], float] = {}
    for metric in ("exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"):
        if metric in summary.columns:
            for dataset, group in summary[summary["n_cases"] > 0].groupby("dataset"):
                values = group[metric].dropna()
                if not values.empty:
                    best[(str(dataset), metric)] = float(values.max())
    headers = [("Config", False), ("Dataset", False), ("Context", False), ("N", True), ("Failed", True)]
    headers += [("Exact", True)]
    if show_category:
        headers += [("Exact, category cases", True)]
    headers += [("hF1", True), ("D1 macro", True), ("D2 macro", True), ("Note", False)]
    rows = []
    for _, r in summary.iterrows():
        failed = bool(str(r.get("error", "")).strip()) or int(r["n_cases"]) == 0  # nothing evaluated: show dashes
        n_ctx = r.get("n_with_context")
        context = str(r["context"])
        if context == "with" and n_ctx is not None and not pd.isna(n_ctx):
            context = f"with ({int(n_ctx)} cases)"
        cells = [
            _td(str(r["config"])),
            _td(str(r["dataset"])),
            _td(context),
            _td(str(int(r["n_cases"])), num=True),
            _td(_count(r.get("n_failed")), num=True),
        ]
        for metric in ("exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"):
            if metric == "h_f1" and show_category:
                n_category, category = r.get("n_category"), r.get("exact_category")
                has_category = not failed and category is not None and not pd.isna(category)
                label = f"{_fmt(category)} (n={_count(n_category)})" if has_category else "—"
                cells.append(_td(label, num=True))
            value = r.get(metric)
            is_best = not failed and (str(r["dataset"]), metric) in best and value == best[(str(r["dataset"]), metric)]
            text = "—" if failed else _esc(_fmt(value))
            lo, hi = _CI_COLUMNS.get(metric, (None, None))
            if lo and lo in r and not failed and not pd.isna(r[lo]) and not pd.isna(r[hi]):
                text += f' <span class="ci">[{_fmt(r[lo], 2)}–{_fmt(r[hi], 2)}]</span>'
            cells.append(_td(text, num=True, best=is_best, raw=True))
        error = str(r.get("error", "")).strip()
        n_failed = r.get("n_failed")
        if error:
            note = f"failed: {error}"
        elif failed:
            note = "no cases evaluated"
        elif n_failed is not None and not pd.isna(n_failed) and int(n_failed) > 0:
            note = f"{int(n_failed)} failed, counted as wrong"
        else:
            note = ""
        cells.append(_td(note, wrap=True))
        rows.append(cells)
    return _table(headers, rows)


def _reliability(summary: pd.DataFrame) -> str:
    """The numbers that put the headline scores in perspective (secondary, so the main table stays narrow)."""
    headers = [("Config", False), ("Dataset", False), ("Context", False), ("Not related", True)]
    headers += [("Unambiguous", True), ("Baseline", True)]
    rows = []
    for _, r in summary.iterrows():
        failed = bool(str(r.get("error", "")).strip()) or int(r["n_cases"]) == 0
        unambiguous = r.get("exact_unambiguous")
        has_unambiguous = not failed and unambiguous is not None and not pd.isna(unambiguous)
        rows.append(
            [
                _td(str(r["config"])),
                _td(str(r["dataset"])),
                _td(str(r["context"])),
                _td("—" if failed or pd.isna(r.get("not_related_rate")) else f"{r['not_related_rate']:.0%}", num=True),
                _td(f"{_fmt(unambiguous)} (n={_count(r.get('n_unambiguous'))})" if has_unambiguous else "—", num=True),
                _td("—" if failed else _fmt(r.get("baseline_exact")), num=True),
            ]
        )
    return "<h3>Reliability</h3>" + _table(headers, rows)


def _narrative_detection(summary: pd.DataFrame) -> str:
    """Denial narrative vs none; empty unless a run included documents annotated as code 0_0."""
    if "rel_f1" not in summary.columns or summary["rel_f1"].isna().all():
        return ""
    headers = [("Config", False), ("Dataset", False), ("Context", False), ("0_0 documents", True)]
    headers += [("Precision", True), ("Recall", True), ("F1", True), ("False alarms", True)]
    rows = [
        [
            _td(str(r["config"])),
            _td(str(r["dataset"])),
            _td(str(r["context"])),
            _td(_count(r.get("n_not_climate")), num=True),
            *(_td(_fmt(r.get(c)), num=True) for c in ("rel_precision", "rel_recall", "rel_f1", "rel_fpr")),
        ]
        for _, r in summary.iterrows()
        if not pd.isna(r["rel_f1"])
    ]
    intro = (
        '<p class="note">Does the classifier find a denial narrative at all? Any CARDS category counts as "narrative", '
        "code 0_0 as none. Scored on every document, including those annotated 0_0 (no climate-misinformation "
        'narrative, whether or not the text is about climate). "False alarms" is the share of 0_0 documents given a '
        "category. The category scores above cover the documents annotated with a category only.</p>"
    )
    return "<h2>Narrative detection</h2>" + intro + _table(headers, rows)


def _ranked_charts(usable: pd.DataFrame) -> str:
    out = []
    only_no_context = bool((usable["context"] == "none").all())  # then the suffix says nothing, so leave it out
    datasets = list(dict.fromkeys(usable["dataset"].astype(str)))
    for metric, title in _METRICS:
        if metric not in usable.columns:
            continue
        lo_col, hi_col = _CI_COLUMNS.get(metric, (None, None))
        for dataset in datasets:
            rows = usable[(usable["dataset"].astype(str) == dataset) & usable[metric].notna()]
            items = []
            for _, r in rows.iterrows():
                nan = float("nan")
                has_interval = (
                    bool(lo_col) and lo_col in rows.columns and not pd.isna(r[lo_col]) and not pd.isna(r[hi_col])
                )
                label = str(r["config"]) if only_no_context else f"{r['config']} · {r['context']} context"
                items.append(
                    (
                        label,
                        float(r[metric]),
                        float(r[lo_col]) if has_interval else nan,
                        float(r[hi_col]) if has_interval else nan,
                    )
                )
            if items:
                suffix = f" · {dataset}" if len(datasets) > 1 else ""
                out.append(f"<h3>{_esc(title + suffix)}</h3>" + ranked_bars_svg(f"{title}, {dataset}", items))
    return "".join(out)


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
    if len(labels) > MAX_SERIES:  # too many series for grouped bars: one ranked chart per dataset and metric
        return _ranked_charts(usable)
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


def _p(p) -> str:
    """An exact p-value to three decimals, or ``<0.001``; a dash when missing."""
    return "—" if p is None or pd.isna(p) else ("<0.001" if p < 0.001 else f"{p:.3f}")


def _p_relation(p) -> str:
    """``= 0.125`` or ``< 0.001``, for running text."""
    text = _p(p)
    return f"< {text[1:]}" if text.startswith("<") else f"= {text}"


def _interval(lo, hi) -> str:
    return "—" if pd.isna(lo) or pd.isna(hi) else f"[{lo:+.3f}, {hi:+.3f}]"


def _verdict(delta, p) -> str:
    """Plain-words reading of a paired difference: significant at 0.05 (with direction), or within noise."""
    if p is None or pd.isna(p) or delta is None or pd.isna(delta):
        return "—"
    if p < 0.05:
        return "significantly better" if delta > 0 else "significantly worse"
    return "within noise"


def _model_rows(cases: pd.DataFrame, summary: pd.DataFrame, baseline: str | None):
    """``((comparison, baseline, mode) | None, note)``: each config against *baseline* in one context mode.

    The default baseline is the first config that has results, so a config that failed outright never blocks the
    report; an explicit baseline without results is explained in the note instead of raising.
    """
    configs = list(dict.fromkeys(summary["config"].astype(str)))
    modes = list(dict.fromkeys(cases["context"])) if not cases.empty else []
    if len(configs) < 2 or not modes:
        return None, ""
    mode = "none" if "none" in modes else modes[0]
    answered = set(cases.loc[cases["context"] == mode, "config"].astype(str))
    with_results = [config for config in configs if config in answered]
    if baseline is not None and baseline not in with_results:
        why = "was not run here" if baseline not in configs else "has no results (it failed)"
        return None, f"Baseline {baseline} {why}, so there is no model comparison."
    baseline = baseline or (with_results[0] if with_results else None)
    if baseline is None or len(with_results) < 2:
        return None, ""
    comparison = compare_configs(cases, baseline, context=mode)
    return (None if comparison.empty else (comparison, baseline, mode)), ""


def _model_note(note: str) -> str:
    return f'<h2>Model comparison</h2><p class="note">{_esc(note)}</p>' if note else ""


def _model_comparison(model_rows) -> str:
    """Each config against the baseline on the cases both answered, in one context mode."""
    if model_rows is None:
        return ""
    comparison, baseline, mode = model_rows
    headers = [("Dataset", False), ("Config", False), ("Paired", True), ("Baseline", True), ("Config exact", True)]
    headers += [("Δ", True), ("Δ 95% CI", True), ("Better", True), ("Worse", True), ("p", True), ("Verdict", False)]
    rows: list[list[str]] = []
    dash = _td("—", num=True)
    for dataset in dict.fromkeys(comparison["dataset"].astype(str)):
        group = comparison[comparison["dataset"].astype(str) == dataset]
        first = group.iloc[0]
        # The baseline gets a row of its own so it is visible, not only named in the sentence above the table.
        rows.append(
            [
                _td(dataset),
                _td(baseline),
                _td(str(int(first["n_paired"])), num=True),
                _td(_fmt(first["exact_baseline"]), num=True),
                _td(_fmt(first["exact_baseline"]), num=True),
                dash,
                dash,
                dash,
                dash,
                dash,
                _td("baseline"),
            ]
        )
        for _, r in group.iterrows():
            rows.append(
                [
                    _td(str(r["dataset"])),
                    _td(str(r["config"])),
                    _td(str(int(r["n_paired"])), num=True),
                    _td(_fmt(r["exact_baseline"]), num=True),
                    _td(_fmt(r["exact_config"]), num=True),
                    _td(f"{r['delta']:+.3f}", num=True),
                    _td(_interval(r["delta_lo"], r["delta_hi"]), num=True),
                    _td(str(int(r["better"])), num=True),
                    _td(str(int(r["worse"])), num=True),
                    _td(_p(r["p_value"]), num=True),
                    _td(_verdict(r["delta"], r["p_value"])),
                ]
            )
    intro = (
        f'<p class="muted">Each config against <b>{_esc(baseline)}</b> on the cases both answered '
        f"(context: {_esc(mode)}). Δ is exact match, config minus baseline; the interval is a 95% bootstrap over the "
        "pairs; p is an exact two-sided McNemar test on the cases where they differ, not corrected for the number of "
        'comparisons. "Within noise" means p is 0.05 or more.</p>'
    )
    return "<h2>Model comparison</h2>" + intro + _table(headers, rows)


def _context_sections(cases: pd.DataFrame) -> str:
    effect = context_effect(cases)
    if effect.empty:
        return ""
    headers = [("Config", False), ("Dataset", False), ("Paired", True), ("None", True), ("With", True), ("Δ", True)]
    headers += [("Δ 95% CI", True), ("Fixed", True), ("Broken", True), ("Same", True), ("p", True), ("Verdict", False)]
    rows = [
        [
            _td(str(r["config"])),
            _td(str(r["dataset"])),
            _td(str(int(r["n_paired"])), num=True),
            _td(_fmt(r["exact_none"]), num=True),
            _td(_fmt(r["exact_with"]), num=True),
            _td(f"{r['delta']:+.3f}", num=True),
            _td(_interval(r["delta_lo"], r["delta_hi"]), num=True),
            _td(str(int(r["fixed"])), num=True),
            _td(str(int(r["broken"])), num=True),
            _td(str(int(r["unchanged"])), num=True),
            _td(_p(r["p_value"]), num=True),
            _td(_verdict(r["delta"], r["p_value"])),
        ]
        for _, r in effect.iterrows()
    ]
    out = [
        "<h2>Context effect</h2>",
        '<p class="muted">Exact match without and with context on the same cases (only cases that carry context). '
        "Fixed: wrong without, right with; broken: the reverse. The interval is a 95% bootstrap over the pairs; p is "
        "an exact two-sided McNemar test on the cases that changed (not corrected for multiple comparisons).</p>",
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


_GLANCE_MODEL_LIMIT = 8  # more models than this and At a glance lists only the significant differences


def _glance(summary: pd.DataFrame, cases: pd.DataFrame, model_rows) -> str:
    """A few plain sentences with the headline results, generated from the data."""
    items: list[str] = []
    usable = summary[(summary["n_cases"] > 0) & summary["exact_match"].notna()]
    for dataset in dict.fromkeys(usable["dataset"].astype(str)):
        group = usable[usable["dataset"].astype(str) == dataset]
        mixed = "n_not_climate" in group.columns and bool((group["n_not_climate"].fillna(0) > 0).any())
        has_category = mixed and "exact_category" in group.columns and group["exact_category"].notna().any()
        metric = "exact_category" if has_category else "exact_match"
        top = group.loc[group[metric].idxmax()]
        scope = f" on the {_count(top.get('n_category'))} cases with a category" if metric == "exact_category" else ""
        text = f"Best exact match on {_esc(dataset)}{scope}: <b>{_esc(str(top['config']))}</b>"
        text += f" ({'with' if top['context'] == 'with' else 'no'} context) at {top[metric]:.3f}"
        if (
            metric == "exact_match"
            and "exact_lo" in top
            and not pd.isna(top["exact_lo"])
            and not pd.isna(top["exact_hi"])
        ):
            text += f" [{top['exact_lo']:.2f}–{top['exact_hi']:.2f}]"
        base = top.get("baseline_exact")
        if metric == "exact_match" and base is not None and not pd.isna(base):
            text += f"; always guessing the most common label scores {base:.3f}"
        items.append(text + ".")
        if "baseline_exact" in group.columns:
            best_per_config = group.sort_values("exact_match", ascending=False).drop_duplicates("config")
            for _, r in best_per_config.iterrows():
                if not pd.isna(r["baseline_exact"]) and r["exact_match"] <= r["baseline_exact"]:
                    items.append(
                        f"<b>{_esc(str(r['config']))}</b> is no better than always guessing the most common label on "
                        f"{_esc(dataset)} ({r['exact_match']:.3f} against {r['baseline_exact']:.3f})"
                        + ("; with many 0_0 documents that label is 0_0." if mixed else ".")
                    )
    if model_rows is not None:
        comparison, baseline, mode = model_rows
        for dataset in dict.fromkeys(comparison["dataset"].astype(str)):
            rows = comparison[comparison["dataset"].astype(str) == dataset]
            verdicts = [_verdict(r["delta"], r["p_value"]) for _, r in rows.iterrows()]
            # A long list of "within noise" lines hides the few differences that matter, so with many models only
            # the significant ones are listed and the rest are counted in one line.
            crowded = len(rows) > _GLANCE_MODEL_LIMIT
            quiet = 0
            for (_, r), verdict in zip(rows.iterrows(), verdicts, strict=True):
                if crowded and not verdict.startswith("significantly"):
                    quiet += 1
                    continue
                items.append(
                    f"<b>{_esc(str(r['config']))}</b> against {_esc(baseline)} on {_esc(dataset)}: "
                    f"{r['delta']:+.3f} exact match ({verdict}, p {_p_relation(r['p_value'])})."
                )
            if quiet:
                items.append(
                    f"{quiet} other model{'s' if quiet != 1 else ''} are within noise of {_esc(baseline)} on "
                    f"{_esc(dataset)} (see Model comparison)."
                )
    effect = context_effect(cases)
    for _, r in effect.iterrows():
        verdict = _verdict(r["delta"], r["p_value"])
        items.append(
            f"Adding context to <b>{_esc(str(r['config']))}</b> on {_esc(str(r['dataset']))}: {r['delta']:+.3f} exact "
            f"match ({verdict}; {int(r['fixed'])} cases fixed, {int(r['broken'])} broken)."
        )
    if not items:
        return ""
    return "<h2>At a glance</h2><ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


_GLOSSARY = (
    ("Exact", "Share of claims where the prediction is one of the acceptable human labels (some claims have a tie)."),
    ("hF1", "Exact match with partial credit through the taxonomy: a near miss (2_1 for 2_3) scores above a far one."),
    ("D1 macro, D2 macro", "F1 averaged over categories at depth 1 (5 main categories) and depth 2 (subcategories)."),
    (
        "Exact, category cases",
        "Exact match on the documents that carry a category, when the dataset also holds 0_0 documents.",
    ),
    ("Failed", "Predictions that errored out. They count as wrong and stay in every denominator."),
    ("Not related", "Share of answered claims predicted as code 0_0 (no denial narrative)."),
    ("Unambiguous", "Exact match on claims with a single acceptable label, where there is no tie to be lenient about."),
    ("Baseline", "Exact match from always guessing the most common label; a score near it means little."),
    ("[a–b]", "95% bootstrap interval over cases. Differences smaller than the interval are noise."),
    ("Δ", "Difference in exact match on the same cases, config minus baseline (or with minus without context)."),
    (
        "p-value",
        "Chance of a difference this large if there were no real one (exact McNemar test on the cases that differ).",
    ),
    ("Fixed / Broken", "Cases wrong without context and right with it, and the reverse."),
)


def _glossary() -> str:
    items = "".join(f"<dt>{_esc(term)}</dt><dd>{_esc(text)}</dd>" for term, text in _GLOSSARY)
    return f"<details><summary>How to read this report</summary><dl>{items}</dl></details>"


def _demote(html_text: str) -> str:
    """Shifts headings one level down (h3 to h4, h2 to h3) so a section can sit inside a benchmark's h2."""
    return html_text.replace("<h3>", "<h4>").replace("</h3>", "</h4>").replace("<h2>", "<h3>").replace("</h2>", "</h3>")


_PLACEHOLDERS = {
    "Narrative detection": "This benchmark has no documents annotated 0_0 (no denial narrative), so nothing to detect.",
    "Size and result": "Needs at least two models with a known size; state size_b for the others in the config.",
    "Model comparison": "Needs at least two models with results on this benchmark.",
    "Context effect": "No model was run with review context on this benchmark.",
}


def _benchmark_body(
    summary: pd.DataFrame, cases: pd.DataFrame, baseline: str | None, placeholders: bool = False
) -> str:
    """The standard sections for one benchmark, always in this order.

    A section without data is left out, or, with ``placeholders`` (reports of several benchmarks), shown with the
    reason, so every benchmark lists the same headings in the same order.
    """
    model_rows, model_note = _model_rows(cases, summary, baseline)

    def standard(heading: str, content: str) -> str:
        if content or not placeholders:
            return content
        return f'<h2>{heading}</h2><p class="muted">{_PLACEHOLDERS[heading]}</p>'

    return (
        f"{_glance(summary, cases, model_rows)}"
        f"<h2>Comparison</h2>{_comparison(summary)}{_reliability(summary)}"
        f"{standard('Narrative detection', _narrative_detection(summary))}"
        f"<h2>Charts</h2>{_charts(summary)}"
        f"{standard('Size and result', _size_section(summary))}"
        f"{standard('Model comparison', _model_comparison(model_rows) or _model_note(model_note))}"
        f"{standard('Context effect', _context_sections(cases))}"
    )


def _overview(summary: pd.DataFrame) -> str:
    """Models by benchmarks in one table: the score each model reached where it was run, a dash where it was not."""
    datasets = list(dict.fromkeys(summary["dataset"].astype(str)))
    configs = list(dict.fromkeys(summary["config"].astype(str)))
    usable = summary[(summary["n_cases"] > 0) & summary["exact_match"].notna()]
    metric_of = {}
    for dataset in datasets:
        group = usable[usable["dataset"].astype(str) == dataset]
        mixed = _has_not_climate(group) and "exact_category" in group.columns and group["exact_category"].notna().any()
        metric_of[dataset] = "exact_category" if mixed else "exact_match"
    cell: dict[tuple[str, str], tuple[float, bool]] = {}
    for (config, dataset), rows in usable.groupby([usable["config"].astype(str), usable["dataset"].astype(str)]):
        row = rows[rows["context"] == "none"].iloc[0] if (rows["context"] == "none").any() else rows.iloc[0]
        value = row[metric_of[dataset]]
        if pd.isna(value):
            continue
        failed = (0 if pd.isna(row.get("n_failed")) else float(row["n_failed"])) / max(float(row["n_cases"]), 1) > 0.10
        cell[(config, dataset)] = (float(value), failed)
    best = {d: max((v for (c, dd), (v, _) in cell.items() if dd == d), default=None) for d in datasets}
    headers = [("Model", False)] + [(d, True) for d in datasets]
    rows_html = []
    for config in configs:
        tds = [_td(config)]
        for dataset in datasets:
            if (config, dataset) not in cell:
                tds.append(_td("—", num=True))
                continue
            value, failed = cell[(config, dataset)]
            tds.append(_td(f"{value:.3f}{' †' if failed else ''}", num=True, best=value == best[dataset]))
        rows_html.append(tds)
    intro = (
        '<p class="muted">Exact match per model and benchmark (context: none where it was run). On benchmarks that '
        "also hold 0_0 documents the score is on the cases that carry a category. Bold: best on that benchmark; "
        "—: not run; †: failed on more than 10% of claims, so the score understates the model.</p>"
    )
    return "<h2>Overview</h2>" + intro + _table(headers, rows_html)


def render_html(runs: Sequence[BenchmarkRun], out_path: str | Path, baseline: str | None = None) -> Path:
    """Renders *runs* as one self-contained HTML report at *out_path* and returns the path.

    With two or more configs a "Model comparison" section compares each against *baseline* (default: the first
    config; ``ValueError`` if it is not one of the configs).
    """
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
    configs = list(dict.fromkeys(summary["config"].astype(str)))
    if baseline is not None and baseline not in configs:
        raise ValueError(f"unknown baseline {baseline!r}; choose one of: {', '.join(configs)}")
    datasets = list(dict.fromkeys(summary["dataset"].astype(str)))
    if len(datasets) == 1:  # one benchmark: the standard sections directly
        body = _benchmark_body(summary, cases, baseline)
    else:  # several: an overview across benchmarks, then the same standard sections for each
        sections = []
        for dataset in datasets:
            part = summary[summary["dataset"].astype(str) == dataset]
            part_cases = cases[cases["dataset"].astype(str) == dataset] if not cases.empty else cases
            sections.append(
                f'<section class="benchmark"><h2>{_esc(dataset)}</h2>'
                f"{_demote(_benchmark_body(part, part_cases, baseline, placeholders=True))}</section>"
            )
        body = _overview(summary) + "".join(sections)
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>CARDS evaluation report</title>'
        f"<style>{_css()}</style></head><body><main><h1>CARDS evaluation report</h1>"
        f'<p class="muted">{len(runs)} run(s), {len(summary)} result row(s), '
        f"{len(datasets)} benchmark{'s' if len(datasets) != 1 else ''}.</p>"
        f"{_glossary()}{caveat}{body}{_details(runs)}</main></body></html>"
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
