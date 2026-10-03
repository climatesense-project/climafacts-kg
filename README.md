# 🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation

![Source code icense](https://img.shields.io/badge/Source_code_license-MIT-blue.svg?style=flat)

![ClimaFactsKG license](https://img.shields.io/badge/ClimaFactsKG_license-CC%20BY%204.0-success.svg?style=flat)

[![CI](https://github.com/climatesense-project/climafacts-kg/actions/workflows/ci.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/ci.yml)
[![Create Release](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml)
[![Publish ClimaFactsKG RDF](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml)

> [ClimaFactsKG](https://purl.net/climatesense/climafactskg/ns) is a knowledge graph designed to combat pervasive climate misinformation by linking 253 common climate myths — available in 28 languages — with scientific corrections and peer-reviewed evidence.
> ClimaFactsKG is integrated with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

Despite the overwhelming scientific evidence supporting the impact of humans on the environment, climate misinformation remains pervasive. This persistent spread of falsehoods is often achieved through the misrepresentation of scientific evidence and the promotion of pseudoscientific narratives that hinder effective climate action. To combat this issue, we introduce [ClimaFactsKG](https://purl.net/climatesense/climafactskg/ns), a knowledge graph that links common climate change denial narratives with scientific corrections. ClimaFactsKG covers 253 unique climate myths (with 1,589 `sc:ClaimReview` entries spanning 28 languages) and links them to 1,205 peer-reviewed `sc:ScholarlyArticle` references drawn from the Skeptical Science literature database. A key feature of ClimaFactsKG is its strategic integration with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base), one of the largest existing misinformation knowledge graphs. This connection allows the interlinking of scientific corrections and climate claims found in CimpleKG and significantly enhances the utility of ClimaFactsKG. By providing a structured and interlinked repository of climate change myths and their scientific rebuttals, ClimaFactsKG offers a valuable resource for researchers studying climate misinformation, fact-checkers seeking reliable counter-evidence, and educators aiming to improve climate literacy.

## 🔍 Knowledge Graph Overview and Documentation

[ClimaFactsKG](https://purl.net/climatesense/climafactskg/ns) uses [`sc:ClaimReview`](https://schema.org/ClaimReview) from the [Schema.org](https://schema.org/) vocabulary to represent claims and scientific corrections collected from the [Skeptical Science](https://skepticalscience.com/) website.
The categorisation of misinforming climate claims is based on the [CARDS](https://cardsclimate.com/) taxonomy. CARDS is used to connect `sc:ClaimReview` between ClimaFactsKG and [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

ClimaFactsKG also integrates the scientific references cited in Skeptical Science articles as structured `sc:ScholarlyArticle` nodes, linking them back to the `sc:ClaimReview` entries that cite them.

### 🔗 RDF Namespaces

The ClimaFactsKG instance-data namespace is: https://purl.net/climatesense/climafactskg/ns#.

The CARDS taxonomy has its own separate namespace: https://purl.net/climatesense/cards/ns#. CARDS is a
shared taxonomy also used to connect claims in [CimpleKG](https://github.com/CIMPLE-project/knowledge-base),
not something owned by ClimaFactsKG specifically, so its concepts (`cards:1_1`, `cards:2_3`, ...) are kept
under their own identity rather than nested inside the ClimaFactsKG namespace.

ClimaFactsKG commonly uses the following namespaces and prefixes:

| Prefix   | URI                                     |
| :------- | :-------------------------------------- |
|          | <https://purl.net/climatesense/climafactskg/ns#>     |
| `cards` | <https://purl.net/climatesense/cards/ns#> |
| `owl` | <http://www.w3.org/2002/07/owl#>        |
| `rdfs` | <http://www.w3.org/2000/01/rdf-schema#> |
| `sc` | <https://schema.org/>                   |
| `skos` | <http://www.w3.org/2004/02/skos/core#>  |
| `bibo` | <http://purl.org/ontology/bibo/>        |
| `cito` | <http://purl.org/spar/cito/>            |
| `xsd`  | <http://www.w3.org/2001/XMLSchema#>     |

### 🗺️ Skeptical Science (SkS) Mappings

The main mappings used to represent the Skeptical Science data in ClimaFactsKG are listed in the following table:

| SkS Article Section            |       | Mapping                                                  | Example Text from SkS Article                                                                                        |
| :----------------------------- | :---- | :--------------------------------------------------------| :------------------------------------------------------------------------------------------------------------------- |
| URL                            | →     | `sc:ClaimReview` / `sc:url` | <https://skepticalscience.com/global-cooling.htm>                                                                    |
| *What the science says...*     | →     | `sc:reviewRating` / `sc:Rating` / `sc:ratingExplanation` | *All the indicators show that global warming is still happening.*                                                    |
| *At a glance*                  | →     | `sc:abstract` | *Earth's surface, oceans and (...).*                                                                                 |
| *Climate Myth...*              | →     | `sc:claimReviewed` / `sc:Claim` / `sc:text` | *It's cooling "In fact global warming has stopped and a cooling is beginning (...).*                                 |
| *Last updated on (...)*        | →     | `sc:dateCreated` | *4 June 2024.*                                                                                                       |
| *by (...)*                     | →     | `sc:author` / `sc:Person` | *John Mason.*                                                                                                        |
| `<meta name="description"/>` | →     | `sc:description` | *Empirical measurements of (...).*                                                                                   |
| `<meta name="keywords"/>` | →     | `sc:keywords` | *global warming, skeptics, skepticism (...).*                                                                        |
| `<title/>` | →     | `sc:name` | *Global cooling - Is global warming still happening?*                                                                |
| Main content                   | →     | `sc:reviewBody` , `sc:text` | *Earth's surface, oceans and atmosphere are all warming due to (...).*                                               |
| Difficulty level (basic / intermediate / advanced) | → | `sc:educationalLevel` | `"basic"` — level-variant `ClaimReview` nodes also carry `rdfs:seeAlso` pointing to the canonical-URL `ClaimReview` |
| *Related Argument*             | →     | `seeAlso` | <https://skepticalscience.com/global-cooling-january-2007-to-january-2008.htm>                                       |
| *source: (...)*                | →     | `sc:citation` | <https://wattsupwiththat.wordpress.com/2008/02/19/january-2008-4-sources-say-globally-cooler-in-the-past-12-months/> |

### 📚 Scientific References Mappings

Scholarly references cited in Skeptical Science articles are extracted from the SkS glossary and mapped to structured RDF using Schema.org as the primary vocabulary, supplemented by BIBO and CiTO:

| Reference Field   |       | Mapping                                                                       |
| :---------------- | :---- | :---------------------------------------------------------------------------- |
| Citation key      | →     | `sc:ScholarlyArticle` URI + `sc:alternateName`                                |
| Title             | →     | `sc:name`                                                                     |
| Authors           | →     | `sc:author` / `sc:Person` / `sc:name` (one node per author)                  |
| Year              | →     | `sc:datePublished`                                                            |
| DOI               | →     | `sc:sameAs` (URI), `sc:identifier` / `sc:PropertyValue`, `bibo:doi`          |
| URL               | →     | `sc:url`                                                                      |
| Journal           | →     | `sc:isPartOf` / `sc:Periodical` + `bibo:Journal`                             |
| Volume            | →     | `sc:isPartOf` / `sc:PublicationVolume` + `bibo:volume`                       |
| Issue             | →     | `sc:isPartOf` / `sc:PublicationIssue` + `bibo:issue`                         |
| Pages             | →     | `sc:pagination`, `sc:pageStart`, `sc:pageEnd`, `bibo:pageStart`, `bibo:pageEnd` |
| Alt keys          | →     | `sc:alternateName` (additional matching terms)                                |

Citation links between `sc:ClaimReview` articles and `sc:ScholarlyArticle` references are generated using keyword matching and represented as `sc:citation` and `cito:cites` triples.

### 📊 Graph Statistics

The following table shows the main entity and triple counts in the current ClimaFactsKG release:

| Entity / Relationship                   | Count   |
| :-------------------------------------- | ------: |
| `sc:ClaimReview` nodes                  | 1,589   |
| `sc:Claim` nodes (unique myths)         | 252     |
| `sc:ScholarlyArticle` / `bibo:AcademicArticle` nodes | 1,205 |
| `sc:Periodical` / `bibo:Journal` nodes  | 420     |
| `sc:Person` nodes (article authors)     | 4,586   |
| `sc:citation` triples (source links)    | 982     |
| `cito:cites` triples (scholarly links)  | 485     |
| Total RDF triples                       | 91,444  |

Run `climafactskg validate` for a live, always-up-to-date count of these figures.

## 🖥️ ClimaFactsKG Source Code

The data and source code releases can be found on the [releases page](https://github.com/climatesense-project/climafacts-kg/releases).

### 📦 Installation

Core install covers `collect`, `build`, `serve`, `export`, and `process --classifier llm` (the LLM-based path). `process`'s *default* classifier is the local two-stage transformer (no API key or cost, matches the pre-refactor pipeline) — that one needs the `transformer` extra below, since it pulls in PyTorch/HuggingFace.

```bash
pip install climafactskg
```

The `matcher` and `transformer` CARDS classifiers, and the annotation-evaluation pipeline, pull in
heavy optional dependencies (spaCy, PyTorch/HuggingFace, Google Sheets/Drive, GEPA). Install only
what you need via extras:

```bash
pip install "climafactskg[matcher]"      # rule-based Jaccard-similarity classifier (spaCy)
pip install "climafactskg[transformer]"  # two-stage HuggingFace classifier (pulls PyTorch)
pip install "climafactskg[eval]"         # CARDS eval/optimization pipeline (GEPA, pydantic-evals, Sheets)
pip install "climafactskg[all]"          # everything
```

With [uv](https://docs.astral.sh/uv/), from a checkout of this repository:

```bash
uv sync --extra matcher --extra transformer --extra eval   # or: --all-extras
```

### ⌨️ Command Line Interface (CLI)

ClimaFactsKG has a simple CLI interface accessible via the `climafactskg` command.

```
 Usage: climafactskg [OPTIONS] COMMAND [ARGS]...

 🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version  -v        Show the installed climafactskg version.                                            │
│ --help               Show this message and exit.                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────╮
│ collect    Collect data for the ClimaFactsKG knowledge graph.                                            │
│ process    Process collected data and store it in the knowledge graph.                                   │
│ build      Build the ClimaFactsKG knowledge graph.                                                       │
│ validate   Validate an RDF graph file (parses OK, non-empty, has ClaimReview nodes). Runs automatically  │
│            at the end of `build` too.                                                                    │
│ classify   Classify text using the CARDS taxonomy.                                                       │
│ serve      Create a SPARQL endpoint for serving a knowledge graph.                                       │
│ export     Export a Preserve database to a JSON file.                                                    │
│ eval       Benchmark and report on the classifiers (`eval run`, `eval context`, `eval report`).          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

`collect` and `process` run their steps independently: a failed step is logged and the others still run, but the command then exits 1, so scripts notice. Page and SPARQL requests time out (`CLIMAFACTSKG_FETCH_TIMEOUT`, 30 s; `CLIMAFACTSKG_SPARQL_TIMEOUT`, 300 s), and an error response is never cached or parsed. `process` classifies with the local transformer engine by default (`--classifier transformer`, requires the `transformer` extra — see Installation above); pass `--classifier llm` to use the LLM-based path instead (core install, see provider table below). `build` merges SkepticalScience, CimpleKG, and ClimateSenseKG data plus the CARDS taxonomy into one `data/climafacts_kg.ttl`.

`process --cache-path` (default: `data/cards_classification_cache.db`) is a Preserve SQLite cache shared across all sources below it in the pipeline (CimpleKG, ClimateSenseKG, SkepticalScience arguments), so identical claim/argument text is classified once instead of once per source. Pass an empty string to disable caching.

#### `classify` — CARDS taxonomy classification

Classifies a text string using one of three available classifiers.

```
 Usage: climafactskg classify [OPTIONS] TEXT

 Classify text using the CARDS taxonomy.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────╮
│ TEXT    Text to classify using CARDS.                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --classifier  -c   TEXT  Classifier: 'transformer' (default), 'matcher', or 'llm'.                      │
│ --preset      -p   TEXT  Named LLM preset (e.g. 'climatesense-nslp'). LLM only.                         │
│ --provider         TEXT  LLM provider ('openai', 'ollama', 'openrouter', 'lmstudio'). LLM only.         │
│ --model       -m   TEXT  LLM model name. LLM only.                                                      │
│ --cache-path       TEXT  Path to a Preserve SQLite cache file. LLM and transformer only.                │
│ --context          TEXT  Optional fact-check context (e.g. reviewer verdict, sources).                 │
│ --no-preclassifier       Disable the ClimateBERT pre-classifier gate. LLM only.                         │
│ --list-presets           Print all registered LLM preset names and exit.                                │
│ --help                   Show this message and exit.                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

**Examples:**

```bash
# Two-stage transformer classifier (default)
climafactskg classify "CO2 is just plant food, not a pollutant"

# Rule-based Jaccard-similarity matcher
climafactskg classify "Global warming stopped in 1998" --classifier matcher

# LLM classifier using a named preset
climafactskg classify "The sun drives all climate change" --classifier llm --preset climatesense-nslp

# LLM classifier with explicit provider and model, with result caching
climafactskg classify "CO2 is just plant food" \
  --classifier llm --provider openai --model gpt-4o-mini --cache-path /tmp/cards.db

# LLM via a local Ollama instance
climafactskg classify "There is no consensus on climate change" \
  --classifier llm --provider ollama --model llama3.3

# List available LLM presets
climafactskg classify "" --list-presets

# With fact-check context (all three classifiers accept it)
climafactskg classify "CO2 is just plant food" --context "Reviewer verdict: false, plants also need water and nutrients"
```

### 🧩 CARDS Classifiers (Python API)

The `climafactskg.classifiers.cards` module exposes three classifiers for programmatic use. All three inherit `CARDSClassifierBase` and share the same interface: `classify(text, context=None) -> str` and `classify_batch(texts, contexts=None) -> list[str]`. `context` is optional fact-check context (e.g. reviewer verdict, sources) — matcher and transformer append it to the text before classifying; the LLM classifier routes it to a dedicated context-aware prompt.

#### Batch classification with context (full or partial)

`classify_batch(texts, contexts)` takes one context per text, in the same order. Use `None` for the items that have no context: each item is classified with its own context if it has one and from the claim text alone otherwise, so a batch can mix both. Passing no `contexts` classifies everything without context. A `contexts` list of a different length than `texts` raises `ValueError`.

```python
from climafactskg.classifiers.cards import CARDSLLMClassifier

clf = CARDSLLMClassifier.from_preset("climatesense-nslp", cache_path="/tmp/cards.db")

texts = [
    "CO2 is just plant food",
    "Global warming stopped in 1998",
    "The Arctic is gaining ice",
]
contexts = [
    "Reviewer verdict: false. Plants also need water and nutrients, and high CO2 lowers crop nutrition.",
    None,  # no review available: classified from the claim alone
    "Reviewer verdict: false. Arctic sea ice extent has declined over the satellite record.",
]
labels = clf.classify_batch(texts, contexts=contexts, concurrency=4)
```

The same call works for the transformer and matcher classifiers, which append the context to the text instead of using a context-aware prompt. Cached results are keyed by claim *and* context, so the with- and without-context answers for one claim are cached separately.

#### Transformer classifier (two-stage, default)

Uses a ClimateBERT-based binary relevance filter followed by a fine-tuned CARDS taxonomy model. No API key required.

```python
from climafactskg.classifiers.cards import CARDSClassifier

clf = CARDSClassifier()
clf.classify("Global warming stopped in 1998")  # → e.g. "1_0"
clf.classify("The weather is nice", context="Reviewer verdict: consistent with rising global temperatures")

# Batch classification with a shared cache (Preserve SQLite), keyed by
# hash(model config | text[+context]) — safe to reuse across collector sources.
clf = CARDSClassifier(cache_path="/tmp/cards.db")
labels = clf.classify_batch(["text one", "text two"])
```

#### Rule-based matcher

Fast Jaccard-similarity lookup against the CARDS taxonomy keyword database. Useful as a lightweight baseline.

```python
from climafactskg.classifiers.cards import CARDSMatcher

clf = CARDSMatcher()
clf.classify("CO2 is not the main driver of warming")  # → e.g. "2_1"
```

#### LLM classifier

Structured-output LLM classifier built on [pydantic-ai](https://github.com/pydantic/pydantic-ai). Supports any OpenAI-compatible provider and includes an optional ClimateBERT pre-filter and [Preserve](https://github.com/kylepollina/preserve) SQLite result cache.

Supported providers:

| Provider string | Backend | Credentials |
| :-------------- | :------ | :---------- |
| `"openai"` | OpenAI API | `OPENAI_API_KEY` env var |
| `"anthropic"` | Anthropic API | `ANTHROPIC_API_KEY` env var |
| `"groq"` | Groq API | `GROQ_API_KEY` env var |
| `"openrouter"` | OpenRouter API | `OPENROUTER_API_KEY` env var |
| `"ollama"` | Local Ollama server | `OLLAMA_BASE_URL` (default: `http://localhost:11434/v1`) |
| `"lmstudio"` | Local LM Studio server | `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`) |

```python
from climafactskg.classifiers.cards import CARDSLLMClassifier

# Default provider/model from CARDS_LLM_PROVIDER / CARDS_LLM_MODEL env vars
clf = CARDSLLMClassifier()
clf.classify("Global warming stopped in 1998")  # → e.g. "1_0"

# Explicit provider and model, with caching
clf = CARDSLLMClassifier(
    provider="openai",
    model="gpt-4o-mini",
    cache_path="/tmp/cards.db",
)

# From a named preset
clf = CARDSLLMClassifier.from_preset("climatesense-nslp", cache_path="/tmp/cards.db")

# List registered presets
from climafactskg.classifiers.cards import registered_presets
print(registered_presets())  # → ('climatesense-nslp', 'xplainnlp-nslp')

# Batch classification (concurrent LLM calls)
labels = clf.classify_batch(["text one", "text two", "text three"], concurrency=4)
```

**Built-in presets:**

| Preset name | Provider | Model |
| :---------- | :------- | :---- |
| `climatesense-nslp` | `openrouter` | `openai/gpt-5.2` |
| `xplainnlp-nslp` | `lmstudio` | `qwen/qwen3-8b` |

Custom presets can be registered with the `@register_preset` decorator:

```python
import dataclasses
from climafactskg.classifiers.cards import CARDSLLMConfig, register_preset

@register_preset("my-preset")
@dataclasses.dataclass
class MyCARDSLLMConfig(CARDSLLMConfig):
    provider: str = "ollama"
    model: str = "llama3.3"
```

### 📏 Evaluation and benchmarking

The `eval` extra adds a pipeline (commands `eval run`, `eval context` and `eval report`; without the extra they print an install hint, and the old names `eval-context` / `eval-report` from 2.2.0 still work) that scores the classifiers against annotated ground truth (the ClimateCheck NSLP data and the ClimateSense annotation rounds `climatesense_v1` / `climatesense_v2`). Metrics are exact match, hierarchical F1 and macro/weighted F1 at taxonomy depth 1 and 2, with 95% bootstrap intervals. A failed prediction counts as wrong and stays in the denominators.

**Review context is opt-in.** ClimateSense claims can be classified with the fact-check's review text as context. Build the context sidecar once (needs the cached consensus CSV and, for CimpleKG reviews, network access), then load datasets with `with_context=True`:

```bash
climafactskg eval context v2            # writes the context sidecar; --force rebuilds it
```

Context is selected deterministically, with no LLM: it drops the claim restatement, verdict fragments and boilerplate, and stops at a sentence boundary within an 800-character budget. Not every claim has a review, so a dataset usually has *partial* context. Cases without context are still evaluated, from the claim alone. Use `only_with_context=True` to restrict a dataset to the covered cases for a like-for-like comparison. By default each classifier is benchmarked in both modes (`none` and `with`), and the report pairs them case by case: fixed/broken counts, a delta with a bootstrap interval, and an exact McNemar p-value.

**Run a benchmark from a config file.** Everything that is benchmarked lives in one TOML file; see [eval.example.toml](eval.example.toml):

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

**Narrative detection (denial narrative or none).** By default the ClimateSense datasets keep only documents annotated with a CARDS category, so the classifier's first decision (any narrative, or code `0_0`) is never tested on a real negative. Set `climate_only = false` on a dataset to include the `0_0` documents (v1: 398 instead of 153, v2: 277 instead of 143). Whenever a dataset has pure `0_0` documents (the NSLP test split does too: 124 of 172), a second "Narrative detection" table (console and HTML report) gives precision, recall, F1 and the false-alarm rate (share of `0_0` documents given a category). Code `0_0` means no climate-misinformation narrative, which covers both text that is not about climate and climate text without a denial narrative, so this is not a pure "climate or not" test. A wrong category on a document that has one is still a correct detection, and a failed prediction counts as wrong. Gold sets that tie `0_0` with a category are left out. The category scores (exact, hF1, F1) cover every case by default, as they did before narrative detection existed (release 2.3.0 briefly excluded the `0_0` documents; they count again, so NSLP numbers match 2.2.0); set `category_scores = "narrative_only"` under `[run]` to score them on the cases that carry a category only. In that mode the `0_0` documents are not written to `cases.csv`, so context and model comparisons stay on the category cases. A mixed run costs more calls, so check `--dry-run` first.

A run that calls a hosted LLM provider (anything except `ollama` / `lmstudio`) first prints how many calls are planned, already cached and new (the cache is checked for free), then asks for confirmation unless `--yes` is given. The LLM result cache is keyed by provider, model, sampling settings and all four prompt templates, so editing a prompt never returns answers produced by the old wording (the first run after upgrading therefore re-asks the model for everything it had cached). The config file is validated up front, so a misspelled key or an unknown dataset option fails before anything is spent. Each run is saved to its own timestamped directory under `save_dir` (`run.json`, `cases.csv`, `summary.csv`, plus a copy of the config); runs are never overwritten. To compare runs or re-render a report later:

```bash
climafactskg eval report data/eval_runs/<run> [<other run> ...] --baseline "gpt-4o-mini"
```

The report is a single self-contained HTML file (no JavaScript or external assets). It opens with an "At a glance" summary written from the data (best result, each model against the baseline, the effect of context, each with a plain-words verdict such as "within noise"), a collapsible "How to read this report" glossary, then the comparison table, charts, paired model comparison, context effect and the cases that changed. The main table also shows exact match on the cases that carry a category whenever a dataset holds `0_0` documents, the model comparison lists the baseline as its own row, and "At a glance" says so when a score is no better than always guessing the most common label (which on a mixed dataset is `0_0`). With many models the charts become a ranked bar chart per metric, so none is dropped. A "Size and result" section plots result against model size (log scale, with the 95% interval and the frontier of models no smaller model beats) once at least two models have a known size. Size is read from the model id when it carries one (`qwen3-235b-a22b` gives 235B with 22B active, `llama-3.3-70b` gives 70B); for models that publish none (closed models, `llama-4-maverick`, `mistral-nemo`) state it per classifier with `size_b` (and `active_b` for a mixture of experts) in the config, and it is saved with the run. Models without a size are listed under the plot, and a hollow marker means the model failed on more than 10% of claims, so its score understates it. The size plots of all benchmarks share one x axis. An "Across benchmarks" section averages each model's scores over the benchmarks (each benchmark counting equally, only models run on all of them), as ranked charts and against model size. Two questions are kept apart everywhere (Overview, tables, charts, size plots): *narrative detection* (does the model find a denial narrative at all, or answer `0_0`; precision, recall and F1) and *category accuracy when a narrative is detected* (exact match of the CARDS category on the claims that have a category and where the model did not answer `0_0`). A missed narrative is a detection error and is not charged to the category score; hierarchical F1 gets the same treatment (hF1 of the category on the claims where a narrative was detected, so a near miss in the right branch earns partial credit). The combined "Exact, category cases" column still shows detection and category together. With more than one benchmark the report opens with an Overview (models by benchmarks, a dash where a model was not run, † where it failed on more than 10% of claims), then gives every benchmark its own section with the same ranked charts, the same table columns (including exact match on the cases with a category) and the same headings in the same order: At a glance, Comparison (with Reliability), Narrative detection, Charts, Size and result, Model comparison and Context effect. A section without data still appears, with the reason, so benchmarks are easy to compare side by side.

### 🧭 Which model to use

These recommendations come from the standard suite ([eval.suite.toml](eval.suite.toml)): 30 LLM configurations plus the transformer and matcher, scored on `climatesense_v1`, `climatesense_v2` and `nslp` with the claim alone (no review context). Scores are averaged over the three benchmarks, each counting equally. The table keeps the two questions apart: *narrative detection* (does the model flag a denial narrative at all) and *category accuracy* (is the CARDS category right on the claims where it did). With about 140 to 400 cases per benchmark, differences of roughly four points are noise, so models within that range of each other are effectively tied.

| You want | Use | Exact category | Narrative-detection F1 | Notes |
| :------- | :-- | :------------- | :--------------------- | :---- |
| Best value, hosted | `deepseek/deepseek-v4-flash` | 0.646 | 0.835 | Open weights (284B, 13B active), about $0.035 per million tokens blended list price, the best category accuracy of all models tested |
| Best at spotting narratives | `nvidia/nemotron-3-super-120b-a12b` | 0.612 | 0.865 | First of all models on narrative detection, about five times the price of deepseek-v4-flash |
| Best closed model | `qwen/qwen3.8-flash` | 0.637 | 0.859 | Needs `output_mode = "prompted"`, see the suite config |
| Best small model (14B) | `mistralai/ministral-14b-2512` | 0.598 | 0.830 | Best model under 15B; fits a 16 GB GPU (T4) or a 16 GB Mac at 4-bit |
| Best on a 32 GB Mac | `google/gemma-4-31b-it` | 0.614 | 0.843 | About 18 GB at 4-bit; `mistral-small-3.2-24b` (0.607) leaves more headroom |
| Free, no API | transformer engine (`process` default) | 0.104 | 0.684 | Far behind every LLM on category accuracy; the matcher is behind as well (0.103, narrative F1 0.236) |

What the full results show:

- **Open weights match closed models.** The best open model beats or ties the best closed one on every score, and `gpt-4o-mini` ranks 15th of 32 (exact category 0.548).
- **Paying more does not help.** The models priced at $0.30 per million tokens or more reach about 0.61, below the cheapest group (about 0.65). Reasoning models cost more than their list price suggests, because they spend many more output tokens per claim.
- **Size matters below about 10B.** Under 10B the scores fall clearly (`qwen3.5-9b` 0.506, `llama-3.1-8b` 0.377). Between 14B and 35B the differences are within noise.
- **Review context does not help on v2.** It lowered exact match for 24 of 32 models, by 3.5 points on average, against gold labels that were annotated from the claim alone.
- **Check the failure count.** A model that cannot follow the output format scores badly without the score saying why. In this run `ling-3.0-flash` answered "no narrative" for almost every claim and `mistral-large-2512` was rate-limited upstream (failed items count as wrong), so neither is a fair comparison. The report shows `n_failed` for every model.

Caveats. The local figures (T4, Mac) are sizes and memory arithmetic: the scores were measured on hosted models, not on quantised local copies, and local speed was not benchmarked, so run a sample on your hardware before relying on it. Prices are the list prices OpenRouter showed at the time of the run and change. The ClimateBERT pre-classifier gate is off in the benchmarks. It matters for the knowledge graph rather than the benchmarks: on a sample of the graph's texts it set aside about 92% as not about climate, so with `--classifier llm` it cuts the number of paid calls sharply (`--no-preclassifier` turns it off), at the cost of dropping about 3% of claims that do carry a narrative (measured on `climatesense_v1`).

## ©️ Licenses

ClimaFactsKG source code is released under the [MIT license](https://opensource.org/license/mit), whereas the knowledge graph is released under the [Creative Commons Attribution 4.0 International (CC-BY 4.0) license](https://creativecommons.org/licenses/by/4.0/).

## 🎓 Citation

Burel, Grégoire and Alani, Harith (2025). *[ClimaFactsKG: Towards an Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation](data/scikworkshop_2025.pdf)*. In: 5th International Workshop on Scientific Knowledge: Representation, Discovery, and Assessment, Nov 2025, Nara, Japan.

```
@inproceedings{Burel2025ClimaFactsKG,
  author    = {Burel, Gr{\'e}goire and Alani, Harith},
  title     = {{ClimaFactsKG}: Towards an Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation},
  booktitle = {5th International Workshop on Scientific Knowledge: Representation, Discovery, and Assessment (Sci-K 2025)},
  series    = {Proceedings of the Workshop on Scientific Knowledge},
  editor    = {TBD}, % Editors of the workshop proceedings
  publisher = {CEUR-WS}, % Common publisher for ISWC workshops
  month     = {November},
  year      = {2025},
  address   = {Nara, Japan},
  note      = {Co-located with ISWC 2025}
}
```
