# Evaluation and benchmarking

This is the full guide to the `eval` pipeline. The README has the short version; the results and what they mean for choosing a model are in [model-selection.md](model-selection.md).

The `eval` extra adds a pipeline (commands `eval run`, `eval context` and `eval report`; without the extra they print an install hint, and the old names `eval-context` / `eval-report` from 2.2.0 still work) that scores the classifiers against annotated ground truth (the ClimateCheck NSLP data and the ClimateSense annotation rounds `climatesense_v1` / `climatesense_v2`). Metrics are exact match, hierarchical F1 and macro/weighted F1 at taxonomy depth 1 and 2, with 95% bootstrap intervals. A failed prediction counts as wrong and stays in the denominators.

## Review context is opt-in

 ClimateSense claims can be classified with the fact-check's review text as context. Build the context sidecar once (needs the cached consensus CSV and, for CimpleKG reviews, network access), then load datasets with `with_context=True`:

```bash
climafactskg eval context v2            # writes the context sidecar; --force rebuilds it
```

Context is selected deterministically, with no LLM: it drops the claim restatement, verdict fragments and boilerplate, and stops at a sentence boundary within an 800-character budget. Not every claim has a review, so a dataset usually has *partial* context. Cases without context are still evaluated, from the claim alone. Use `only_with_context=True` to restrict a dataset to the covered cases for a like-for-like comparison. By default each classifier is benchmarked in both modes (`none` and `with`), and the report pairs them case by case: fixed/broken counts, a delta with a bootstrap interval, and an exact McNemar p-value.

## Run a benchmark from a config file

 Everything that is benchmarked lives in one TOML file; see [eval.example.toml](../eval.example.toml):

```toml
[run]
save_dir = "data/eval_runs"
context_modes = ["none", "with"]
# category_scores = "all"        # or "narrative_only", see below

[defaults]                       # applied to every LLM classifier
provider = "openrouter"
preset = "xplainnlp-nslp"
cache_path = "data/eval_cache.db"

[[classifiers]]
label = "gpt-4o-mini"
model = "openai/gpt-4o-mini"

[[classifiers]]
label = "llama-4-maverick"
model = "meta-llama/llama-4-maverick"
size_b = 400                     # not in the model id, so stated here for the size plot
active_b = 17                    # mixture of experts: parameters active per token

[[classifiers]]
label = "transformer"
engine = "transformer"           # also: "matcher"

[[datasets]]
name = "climatesense_v2"
with_context = true              # partial context: cases without a review are claim-only
```

```bash
climafactskg eval run eval.toml --dry-run   # show cases per dataset and paid calls: planned, already cached, new
climafactskg eval run eval.toml --report    # run, save, and write report.html next to the results
climafactskg eval run eval.toml --yes       # skip the confirmation before paid LLM calls
```

## Narrative detection (denial narrative or none)

 By default the ClimateSense datasets keep only documents annotated with a CARDS category, so the classifier's first decision (any narrative, or code `0_0`) is never tested on a real negative. Set `climate_only = false` on a dataset to include the `0_0` documents (v1: 398 instead of 153, v2: 277 instead of 143). Whenever a dataset has pure `0_0` documents (the NSLP test split does too: 124 of 172), a second "Narrative detection" table (console and HTML report) gives precision, recall, F1 and the false-alarm rate (share of `0_0` documents given a category). Code `0_0` means no climate-misinformation narrative, which covers both text that is not about climate and climate text without a denial narrative, so this is not a pure "climate or not" test. A wrong category on a document that has one is still a correct detection, and a failed prediction counts as wrong. Gold sets that tie `0_0` with a category are left out. The category scores (exact, hF1, F1) cover every case by default, as they did before narrative detection existed (release 2.3.0 briefly excluded the `0_0` documents; they count again, so NSLP numbers match 2.2.0); set `category_scores = "narrative_only"` under `[run]` to score them on the cases that carry a category only. In that mode the `0_0` documents are not written to `cases.csv`, so context and model comparisons stay on the category cases. A mixed run costs more calls, so check `--dry-run` first.

## Cost guard, caching and saved runs

A run that calls a hosted LLM provider (anything except `ollama` / `lmstudio`) first prints how many calls are planned, already cached and new (the cache is checked for free), then asks for confirmation unless `--yes` is given. The LLM result cache is keyed by provider, model, sampling settings and all four prompt templates, so editing a prompt never returns answers produced by the old wording (the first run after upgrading therefore re-asks the model for everything it had cached). The config file is validated up front, so a misspelled key or an unknown dataset option fails before anything is spent. Each run is saved to its own timestamped directory under `save_dir` (`run.json`, `cases.csv`, `summary.csv`, plus a copy of the config); runs are never overwritten. To compare runs or re-render a report later:

```bash
climafactskg eval report data/eval_runs/<run> [<other run> ...] --baseline "gpt-4o-mini"
```

## The HTML report

The report is a single self-contained HTML file (no JavaScript or external assets). It opens with an "At a glance" summary written from the data (best result, each model against the baseline, the effect of context, each with a plain-words verdict such as "within noise"), a collapsible "How to read this report" glossary, then the comparison table, charts, paired model comparison, context effect and the cases that changed. The main table also shows exact match on the cases that carry a category whenever a dataset holds `0_0` documents, the model comparison lists the baseline as its own row, and "At a glance" says so when a score is no better than always guessing the most common label (which on a mixed dataset is `0_0`). With many models the charts become a ranked bar chart per metric, so none is dropped. A "Size and result" section plots result against model size (log scale, with the 95% interval and the frontier of models no smaller model beats) once at least two models have a known size. Size is read from the model id when it carries one (`qwen3-235b-a22b` gives 235B with 22B active, `llama-3.3-70b` gives 70B); for models that publish none (closed models, `llama-4-maverick`, `mistral-nemo`) state it per classifier with `size_b` (and `active_b` for a mixture of experts) in the config, and it is saved with the run. Models without a size are listed under the plot, and a hollow marker means the model failed on more than 10% of claims, so its score understates it. The size plots of all benchmarks share one x axis. An "Across benchmarks" section averages each model's scores over the benchmarks (each benchmark counting equally, only models run on all of them), as ranked charts and against model size. Two questions are kept apart everywhere (Overview, tables, charts, size plots): *narrative detection* (does the model find a denial narrative at all, or answer `0_0`; precision, recall and F1) and *category accuracy when a narrative is detected* (exact match of the CARDS category on the claims that have a category and where the model did not answer `0_0`). A missed narrative is a detection error and is not charged to the category score; hierarchical F1 gets the same treatment (hF1 of the category on the claims where a narrative was detected, so a near miss in the right branch earns partial credit). The combined "Exact, category cases" column still shows detection and category together. With more than one benchmark the report opens with an Overview (models by benchmarks, a dash where a model was not run, † where it failed on more than 10% of claims), then gives every benchmark its own section with the same ranked charts, the same table columns (including exact match on the cases with a category) and the same headings in the same order: At a glance, Comparison (with Reliability), Narrative detection, Charts, Size and result, Model comparison and Context effect. A section without data still appears, with the reason, so benchmarks are easy to compare side by side.
