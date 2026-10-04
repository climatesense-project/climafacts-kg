# Evaluation and Benchmarking

This guide documents the classifier evaluation and benchmarking pipeline (`climafactskg eval`). For comprehensive benchmark findings and model recommendations, see [model-selection.md](model-selection.md).

The `eval` extra provides tooling to benchmark classifiers against annotated ground truth (including the ClimateCheck NSLP dataset and the ClimateSense annotation rounds `climatesense_v1` and `climatesense_v2`):

```bash
pip install "climafactskg[eval] @ git+https://github.com/climatesense-project/climafacts-kg.git"
```

Metrics computed include exact match, hierarchical F1 (hF1), and macro/weighted F1 at taxonomy depths 1 and 2, with 95% bootstrap confidence intervals. Failed API calls are scored as incorrect.

---

## 🔍 Review Context (Optional)

ClimateSense claims can be evaluated with or without accompanying fact-check review text as context.

Generate the deterministic context sidecar:

```bash
climafactskg eval context v2   # Writes the context sidecar; use --force to rebuild
```

**Context Selection Properties:**
- Context is selected deterministically without LLM generation: claim restatements, verdict markers, and boilerplate are stripped, truncating at a sentence boundary within an 800-character budget.
- Because not every claim has an available review, datasets contain partial context. Items without reviews fall back to claim-only evaluation.
- Set `only_with_context = true` in benchmark configurations to restrict evaluation strictly to items with available context.
- When evaluating with and without context, reports provide paired case-by-case comparisons: deltas, bootstrap intervals, and McNemar statistical tests.

---

## ⚙️ Configuration-Driven Benchmarking

Benchmark suites are defined in TOML configuration files (see [eval.example.toml](../eval.example.toml)):

```toml
[run]
save_dir = "data/eval_runs"
context_modes = ["none", "with"]

[defaults]
provider = "openrouter"
preset = "xplainnlp-nslp"
cache_path = "data/eval_cache.db"

[[classifiers]]
label = "gpt-4o-mini"
model = "openai/gpt-4o-mini"

[[classifiers]]
label = "transformer"
engine = "transformer"

[[datasets]]
name = "climatesense_v2"
with_context = true
```

### CLI Execution

```bash
# Preview planned calls, cached results, and estimated expenditure
climafactskg eval run eval.toml --dry-run

# Execute benchmark and generate self-contained HTML report
climafactskg eval run eval.toml --report

# Bypass interactive prompt before incurring API calls
climafactskg eval run eval.toml --yes
```

---

## 🎯 Narrative Detection vs Category Accuracy

CARDS code `0_0` represents "no climate-misinformation narrative". Consequently, evaluation distinguishes two distinct evaluation dimensions:

1. **Narrative Detection (Binary Screening):**
   - Tests whether a model correctly detects the presence of any misinformation narrative versus predicting `0_0`.
   - Measured by precision, recall, F1, and the **false-alarm rate** (share of `0_0` negative documents incorrectly assigned a category).
   - By default, datasets include documents annotated with code `0_0`. Set `climate_only = true` on a dataset to restrict evaluation exclusively to narrative-bearing claims.

2. **Category Accuracy (Taxonomy Classification):**
   - Measures exact match and hierarchical F1 over claims that genuinely contain a narrative.
   - A missed narrative (predicting `0_0` for a true narrative) is counted as an incorrect classification.

---

## 🛡️ Caching and Cost Protection

- **Pre-execution Audit:** Before making calls to hosted providers, the CLI audits the cache and displays counts for planned, cached, and new calls, prompting for confirmation unless `--yes` is specified.
- **Robust Cache Keying:** The SQLite cache is keyed by provider, model, sampling parameters, and prompt templates. Prompt modifications automatically invalidate outdated entries.
- **Persistent Artefacts:** Each run is saved to an immutable, timestamped directory under `save_dir`, containing `run.json`, `cases.csv`, `summary.csv`, and a snapshot of the input configuration.

---

## 📊 Generating Reports

Compare multiple runs or render reports post hoc:

```bash
climafactskg eval report data/eval_runs/<run_dir> --baseline "gpt-4o-mini"
```

The resulting standalone HTML report (free of external JavaScript or remote CDN dependencies) provides:

* **Executive Summary:** Highlights the leading models, baseline deltas, and statistical significance indicators.
* **Comparative Metric Tables:** Breaks down exact match, hierarchical F1, and narrative detection metrics across benchmarks.
* **Pareto Frontier Plots:** Evaluates performance against model parameter size (logarithmic scale) and inference cost.
* **Context Impact Analysis:** Visualises whether review context improved or hindered performance for each architecture.
* **Case-Level Error Diffs:** Details specific claims where classifications diverged between models or configurations.
