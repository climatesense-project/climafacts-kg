"""Rebuild the plots and ``results.csv`` of ``docs/model-selection.md`` from a saved ``eval run``.

Usage::

    python docs/model-selection/make_plots.py data/eval_runs/<run>

The run folder must hold ``cases.csv``, ``summary.csv`` and ``run.json`` (what ``climafactskg eval run`` saves) for the
standard suite (``eval.suite.toml``). The charts are plain SVG files with a solid background, so they read the same on
a light or a dark page.
"""

import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from climafactskg.classifiers.cards.report import _SERIES_LIGHT, ranked_bars_svg, size_scatter_svg

OUT = Path(__file__).parent
NO_NARRATIVE = {"0", "0_0"}
# Models left out of the charts: ling-3.0-flash answers "no narrative" for nearly every claim and mistral-large-2512
# still had failed items (rate limits), so neither score is a fair measure of the model.
EXCLUDED = {"ling-3.0-flash", "mistral-large-2512"}
# Cost per call in USD, measured as the change in the OpenRouter account's usage over 24 real claims each.
COST_PER_CALL = {
    "glm-5.3-flash": 0.00009,
    "ministral-14b-2512": 0.00010,
    "glm-4.7-flash": 0.00030,
    "qwen3.8-flash": 0.00033,
    "gemma-4-31b": 0.00039,
    "deepseek-v4-flash": 0.0017,
}
CSS = (
    ".chart text{fill:#52514e;font-size:11px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif}"
    ".chart .grid{stroke:#dcdbd6;stroke-width:1;fill:none}.chart .err{stroke:#52514e;stroke-width:1.5;fill:none}"
    ".chart .frontier{stroke:#52514e;stroke-width:1.5;stroke-dasharray:4 3;fill:none}"
    f".chart .dot{{fill:{_SERIES_LIGHT[0]};stroke:#fcfcfb;stroke-width:2}}"
    f".chart .dot.hollow{{fill:#fcfcfb;stroke:{_SERIES_LIGHT[0]}}}.chart .s0{{fill:{_SERIES_LIGHT[0]}}}"
    ".chart .hl{fill:#eb6834}.chart .axis{fill:#0b0b0b;font-size:12px}"
)


def standalone(svg: str) -> str:
    """Give an inline report chart its own style block and a solid background."""
    head, rest = svg.split(">", 1)
    view = head.split('viewBox="0 0 ')[1].split('"')[0].split()
    background = f'<rect width="{view[0]}" height="{view[1]}" fill="#fcfcfb"/>'
    return f"{head}><style>{CSS}</style>{background}{rest}".replace('class="chart wide"', 'class="chart"')


def gold(value: str) -> set[str]:
    """The acceptable gold labels of a ``cases.csv`` row, which stores tied labels as ``"5_0;2_0;0_0"``."""
    return {label.strip() for label in value.split(";")}


def scores(run: Path) -> dict[str, dict]:
    """Pooled category accuracy, false-alarm rate and their equally weighted balanced score, with 95% intervals."""
    categories: dict[str, list[float]] = defaultdict(list)
    alarms: dict[str, list[float]] = defaultdict(list)
    with open(run / "cases.csv", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["context"] != "none":
                continue
            labels = gold(row["gold"])
            if labels <= NO_NARRATIVE:
                alarms[row["config"]].append(0.0 if row["pred"] in NO_NARRATIVE | {"", "None"} else 1.0)
            elif not labels & NO_NARRATIVE:
                categories[row["config"]].append(float(float(row["exact"]) >= 1))
    out = {}
    for config in categories:
        cat, alarm = categories[config], alarms[config]
        rng = random.Random(3)
        boot = sorted(
            (statistics.mean(rng.choices(cat, k=len(cat))) + 1 - statistics.mean(rng.choices(alarm, k=len(alarm)))) / 2
            for _ in range(1000)
        )
        out[config] = {
            "category_accuracy": statistics.mean(cat),
            "false_alarm_rate": statistics.mean(alarm),
            "balanced": (statistics.mean(cat) + 1 - statistics.mean(alarm)) / 2,
            "balanced_lo": boot[25],
            "balanced_hi": boot[974],
            "n_narrative": len(cat),
            "n_no_narrative": len(alarm),
        }
    return out


def averages(run: Path) -> dict[str, dict]:
    """Each config's mean over the benchmarks of the summary scores, plus its failed-item count."""
    columns = ("exact_category", "exact_detected", "hf1_detected", "rel_f1")
    rows: dict[str, list[dict]] = defaultdict(list)
    with open(run / "summary.csv", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["context"] == "none":
                rows[row["config"]].append(row)
    out = {}
    for config, items in rows.items():
        out[config] = {c: statistics.mean(float(r[c]) for r in items) for c in columns}
        out[config]["n_failed"] = sum(float(r["n_failed"]) for r in items)
    return out


def scatter(
    title: str,
    points: list[tuple[str, float, float]],
    x_label: str,
    y_label: str,
    x_log: bool,
    x_ticks,
    *,
    y_range=(0.45, 0.8),
) -> str:
    """A labelled scatter plot (``points`` are ``(label, x, y)``) with a linear or log x axis."""
    width, height, left, right, top, bottom = 900, 440, 62, 30, 20, 50
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = [p[1] for p in points]

    def tx(value: float) -> float:
        return math.log10(value) if x_log else value

    lo, hi = tx(min(xs)), tx(max(xs))
    pad = (hi - lo) * 0.08 or 0.1
    lo, hi = lo - pad, hi + pad
    y_lo, y_hi = y_range

    def x_of(value: float) -> float:
        return left + plot_w * (tx(value) - lo) / (hi - lo)

    def y_of(value: float) -> float:
        return top + plot_h * (1 - (value - y_lo) / (y_hi - y_lo))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{title}"><title>{title}</title>'
    ]
    steps = 5
    for n in range(steps + 1):
        value = y_lo + (y_hi - y_lo) * n / steps
        parts.append(f'<path class="grid" d="M{left},{y_of(value):.1f} H{width - right}"/>')
        parts.append(f'<text x="{left - 6}" y="{y_of(value) + 4:.1f}" text-anchor="end">{value:.2f}</text>')
    for tick, text in x_ticks:
        if lo <= tx(tick) <= hi:
            parts.append(f'<path class="grid" d="M{x_of(tick):.1f},{top} V{top + plot_h}"/>')
            parts.append(f'<text x="{x_of(tick):.1f}" y="{top + plot_h + 16}" text-anchor="middle">{text}</text>')
    parts.append(
        f'<text class="axis" x="{left + plot_w / 2:.1f}" y="{height - 8}" text-anchor="middle">{x_label}</text>'
    )
    parts.append(
        f'<text class="axis" transform="rotate(-90)" x="{-(top + plot_h / 2):.1f}" y="14" '
        f'text-anchor="middle">{y_label}</text>'
    )
    placed = [(x_of(x) - 7, x_of(x) + 7, y_of(y) - 7, y_of(y) + 7) for _, x, y in points]
    for label, x, y in sorted(points, key=lambda p: p[1]):
        cx, cy = x_of(x), y_of(y)
        parts.append(
            f'<g><title>{label}: {x:g}, {y:.3f}</title><circle class="dot" cx="{cx:.1f}" cy="{cy:.1f}" r="5"/></g>'
        )
        text_w = 6.2 * len(label)
        for dx, dy, anchor in (
            (8, 4, "start"),
            (8, -9, "start"),
            (8, 17, "start"),
            (-8, 4, "end"),
            (-8, -9, "end"),
            (-8, 17, "end"),
            (8, -22, "start"),
            (8, 30, "start"),
        ):
            x0 = cx + dx if anchor == "start" else cx + dx - text_w
            box = (x0, x0 + text_w, cy + dy - 10, cy + dy + 3)
            if (
                left <= box[0]
                and box[1] <= width - right
                and not any(box[0] < b[1] and b[0] < box[1] and box[2] < b[3] and b[2] < box[3] for b in placed)
            ):
                break
        placed.append(box)
        parts.append(f'<text x="{cx + dx:.1f}" y="{cy + dy:.1f}" text-anchor="{anchor}">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)


def main(run: Path) -> None:
    """Write ``results.csv`` and the four SVG charts next to this script."""
    pooled, mean = scores(run), averages(run)
    sizes = {}
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))["configs"]
    for config in meta if isinstance(meta, list) else [{"label": k, **v} for k, v in meta.items()]:
        sizes[config.get("label") or config.get("config")] = (config.get("size_b"), config.get("active_b"))

    fields = [
        "model",
        "balanced",
        "balanced_lo",
        "balanced_hi",
        "category_accuracy",
        "false_alarm_rate",
        "exact_category",
        "exact_detected",
        "hf1_detected",
        "narrative_f1",
        "failed_items",
        "size_b",
        "active_b",
        "cost_per_call_usd",
    ]
    rows = []
    for config in sorted(pooled, key=lambda c: -pooled[c]["balanced"]):
        p, m = pooled[config], mean[config]
        size, active = sizes.get(config, (None, None))
        rows.append(
            {
                "model": config,
                "balanced": round(p["balanced"], 4),
                "balanced_lo": round(p["balanced_lo"], 4),
                "balanced_hi": round(p["balanced_hi"], 4),
                "category_accuracy": round(p["category_accuracy"], 4),
                "false_alarm_rate": round(p["false_alarm_rate"], 4),
                "exact_category": round(m["exact_category"], 4),
                "exact_detected": round(m["exact_detected"], 4),
                "hf1_detected": round(m["hf1_detected"], 4),
                "narrative_f1": round(m["rel_f1"], 4),
                "failed_items": int(m["n_failed"]),
                "size_b": size or "",
                "active_b": active or "",
                "cost_per_call_usd": COST_PER_CALL.get(config, ""),
            }
        )
    with open(OUT / "results.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    shown = [r for r in rows if r["model"] not in EXCLUDED]
    items = [(r["model"], r["balanced"], r["balanced_lo"], r["balanced_hi"]) for r in shown]
    (OUT / "balanced_ranking.svg").write_text(
        standalone(ranked_bars_svg("Balanced score by model (95% interval)", items, width=760)), encoding="utf-8"
    )

    points = [
        {
            "label": r["model"],
            "size": float(r["size_b"]),
            "active": float(r["active_b"]) if r["active_b"] != "" else None,
            "value": r["balanced"],
            "lo": r["balanced_lo"],
            "hi": r["balanced_hi"],
            "flag": False,
        }
        for r in shown
        if r["size_b"] != ""
    ]
    (OUT / "balanced_vs_size.svg").write_text(
        standalone(size_scatter_svg("Balanced score against model size", points, y_label="Balanced score")),
        encoding="utf-8",
    )

    # The transformer and matcher baselines (category accuracy about 0.1) would sit far below the range of the models.
    trade = [
        (r["model"], r["false_alarm_rate"], r["category_accuracy"]) for r in shown if r["category_accuracy"] >= 0.3
    ]
    (OUT / "tradeoff.svg").write_text(
        standalone(
            scatter(
                "Category accuracy against false-alarm rate",
                trade,
                "False-alarm rate on documents with no narrative (lower is better)",
                "Category accuracy on documents with a narrative",
                False,
                [(v / 100, f"{v}%") for v in (0, 5, 10, 15, 20, 25, 30)],
                y_range=(0.3, 0.7),
            )
        ),
        encoding="utf-8",
    )

    cost = [(r["model"], float(r["cost_per_call_usd"]), r["balanced"]) for r in shown if r["cost_per_call_usd"] != ""]
    (OUT / "cost_vs_score.svg").write_text(
        standalone(
            scatter(
                "Balanced score against measured cost per call",
                cost,
                "Measured cost per call (USD, log scale)",
                "Balanced score",
                True,
                [(v, f"${v:g}") for v in (0.0001, 0.0003, 0.001, 0.003)],
                y_range=(0.6, 0.76),
            )
        ),
        encoding="utf-8",
    )
    print(f"wrote results.csv and 4 charts for {len(shown)} models to {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
