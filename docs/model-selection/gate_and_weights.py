"""Recompute the balanced score with the ClimateBERT gate simulated and with other weightings.

Usage (needs the ``transformer`` extra for the gate model)::

    python docs/model-selection/gate_and_weights.py data/eval_runs/<run>

The gate's answer depends only on the text, so its effect on any model can be simulated from a saved run: a document the
gate calls not climate-related is predicted ``0_0`` (the classifier returns the "no narrative" code without calling the
LLM). The balanced score is ``w * category accuracy + (1 - w) * (1 - false-alarm rate)``.
"""

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

from climafactskg.classifiers.climate import ClimateBertClassifier

NO_NARRATIVE = {"0", "0_0"}
EXCLUDED = {"ling-3.0-flash", "mistral-large-2512", "transformer", "matcher"}


def kind(gold: str) -> str:
    """Classify a gold set as ``neg`` (only no-narrative), ``cat`` (a category, no ``0_0``) or ``tie`` (both)."""
    labels = {label.strip() for label in gold.split(";")}
    if labels <= NO_NARRATIVE:
        return "neg"
    return "cat" if not labels & NO_NARRATIVE else "tie"


def metrics(rows: list[dict], config: str, gate: dict[str, str] | None) -> tuple[float, float]:
    """``(category accuracy, false-alarm rate)`` of one config, with the gate applied when ``gate`` is given."""
    cats: list[float] = []
    alarms: list[float] = []
    for row in rows:
        if row["config"] != config or kind(row["gold"]) == "tie":
            continue
        gated = gate is not None and gate[row["text"]] == "no"
        prediction = "0_0" if gated else row["pred"]
        if kind(row["gold"]) == "neg":
            alarms.append(0.0 if prediction in NO_NARRATIVE | {"", "None"} else 1.0)
        else:
            cats.append(float(not gated and float(row["exact"]) >= 1))
    return statistics.mean(cats), statistics.mean(alarms)


def main(run: Path) -> None:
    """Print where the gate acts and how the ranking moves with the gate and the weighting."""
    with open(run / "cases.csv", encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["context"] == "none"]
    texts = sorted({row["text"] for row in rows})
    gate_model = ClimateBertClassifier()
    gate: dict[str, str] = {}
    for start in range(0, len(texts), 32):
        chunk = texts[start : start + 32]
        gate.update(zip(chunk, gate_model.classify_batch(chunk), strict=True))

    one = next(row["config"] for row in rows)
    counts = Counter((r["dataset"], kind(r["gold"]), gate[r["text"]]) for r in rows if r["config"] == one)
    print("documents the gate keeps (yes) or drops (no), by dataset and gold kind:")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")

    configs = sorted({row["config"] for row in rows} - EXCLUDED)
    for label, applied in (("gate off", None), ("gate on (simulated)", gate)):
        print(f"\n{label}")
        results = {config: metrics(rows, config, applied) for config in configs}
        for weight in (0.3, 0.5, 0.75):
            ranked = sorted(results, key=lambda c: -(weight * results[c][0] + (1 - weight) * (1 - results[c][1])))
            top = ", ".join(
                f"{c} {weight * results[c][0] + (1 - weight) * (1 - results[c][1]):.3f}" for c in ranked[:6]
            )
            print(f"  weight on category accuracy {weight}: {top}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
