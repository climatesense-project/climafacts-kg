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

### 🏷️ Classifier Provenance

Each CARDS label is the existing `schema:about` link (and its reverse `schema:subjectOf`), which is unchanged. The model that produced the labels is described next to it, from the tag stored with each classified entry, with one `schema:AssessAction` per distinct tag:

| Stored tag | → | Mapping |
| :--------- | :- | :------ |
| one per distinct tag | → | `:classification_<md5 of the tag>` `a schema:AssessAction` with a `schema:name` |
| each model that ran (the LLM, the gate model, or the transformer's two stages) | → | `schema:instrument` `:model_<md5 of the model id>` `a schema:SoftwareApplication`, `schema:name` = the model id |
| each review that carries a label from that classifier | → | `schema:object` pointing at the review's own IRI |

```turtle
:classification_34368a354ffd368cd4848231b844379a
    a schema:AssessAction ;
    schema:name "CARDS labelling, two-stage transformer" ;
    schema:instrument :model_0393bb74e1266405570ef25d42565c6b, :model_34e9248425d7d6b866b21c111863e2c5 ;
    schema:object :claimreview_b9ba07b8af9a5410fdc5cb7be7acb708 .
:model_0393bb74e1266405570ef25d42565c6b a schema:SoftwareApplication ; schema:name "crarojasca/BinaryAugmentedCARDS" .
```

Reviews with no tag, or with a bare preset name (older runs did not record the model), get no description rather than a guessed one, and a review with no CARDS link gets nothing, as before. The nodes follow the graph's `<type>_<md5>` convention and add one triple per labelled review.

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
| `sc:ClaimReview` nodes                  | 1,588   |
| `sc:Claim` nodes (unique myths)         | 252     |
| `sc:ScholarlyArticle` / `bibo:AcademicArticle` nodes | 1,205 |
| `sc:Periodical` / `bibo:Journal` nodes  | 420     |
| `sc:Person` nodes (article authors)     | 4,585   |
| `sc:citation` triples (source links)    | 982     |
| `cito:cites` triples (scholarly links)  | 485     |
| CARDS labels (`schema:about` links to a `cards:` concept, each with its reverse `schema:subjectOf`) | 6,012 |
| `sc:AssessAction` nodes (classifier descriptions, see Classifier Provenance above) | 1 |
| `sc:SoftwareApplication` nodes (models that produced the labels) | 2 |
| Total RDF triples                       | 95,158  |

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

`collect` and `process` run their steps independently: a failed step is logged and the others still run, but the command then exits 1, so scripts notice. Page and SPARQL requests time out (`CLIMAFACTSKG_FETCH_TIMEOUT`, 30 s; `CLIMAFACTSKG_SPARQL_TIMEOUT`, 300 s), and an error response is never cached or parsed (the one exception: the Skeptical Science misinformers page is served complete but with a 404 status, so `collect` accepts that status for it only, and fails if the page then lists no misinformers). `process` classifies with the local transformer engine by default (`--classifier transformer`, requires the `transformer` extra — see Installation above); pass `--classifier llm` to use the LLM-based path instead (core install, see provider table below). `build` merges SkepticalScience, CimpleKG, and ClimateSenseKG data plus the CARDS taxonomy into one `data/climafacts_kg.ttl`.

`process --classifier llm` runs the `xplainnlp-nslp` preset as defined (a local LM Studio model, ClimateBERT gate off) unless told otherwise: `--preset`, `--provider` and `--model` choose another preset, provider and model, and `--preclassifier` / `--no-preclassifier` turn the gate on or off (all four need `--classifier llm`; without them nothing changes). Whatever the options, the provenance tag stored with each classified entry records the model that actually ran, for example `xplainnlp-nslp|openrouter/google/gemma-4-31b-it`, with the gate model appended when the gate is on (`...+climatebert/distilroberta-base-climate-detector`); the transformer engine's tag is `transformer:<binary model>,<taxonomy model>`. Example: `climafactskg process --classifier llm --provider openrouter --model google/gemma-4-31b-it --preclassifier --concurrency 24`.

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
print(registered_presets())  # → ('climatesense-nslp', 'xplainnlp-nslp', 'xplainnlp-nslp-tuned', 'cards-narrative')

# Batch classification (concurrent LLM calls)
labels = clf.classify_batch(["text one", "text two", "text three"], concurrency=4)
```

**Built-in presets:**

| Preset name | Provider | Model |
| :---------- | :------- | :---- |
| `climatesense-nslp` | `openrouter` | `openai/gpt-5.2` |
| `xplainnlp-nslp` | `lmstudio` | `qwen/qwen3-8b-mlx` |
| `xplainnlp-nslp-tuned` | `lmstudio` | `qwen/qwen3-8b-mlx` (experimental: `xplainnlp-nslp` with a GEPA-tuned system prompt, see the results under "Which model to use") |
| `cards-narrative` | `CARDS_LLM_PROVIDER` (default `openai`) | `CARDS_LLM_MODEL` (default `gpt-4o-mini`); classifies the narrative a claim promotes, not its surface wording |

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

### 🧭 Which model to use

The full write-up, with charts, the measured costs and the caveats, is in [docs/model-selection.md](docs/model-selection.md). How to run the benchmarks yourself is in [docs/evaluation.md](docs/evaluation.md). Its main finding is that no model is clearly the best: about the top ten LLMs are statistically tied, so the choice is a matter of cost, speed and which kind of mistake you can tolerate.

These recommendations come from the standard suite ([eval.suite.toml](eval.suite.toml)): 30 LLM configurations plus the transformer and matcher, scored on `climatesense_v1`, `climatesense_v2` and `nslp` with the claim alone (no review context). Scores are averaged over the three benchmarks, each counting equally. The table keeps the two questions apart: *narrative detection* (does the model flag a denial narrative at all) and *category accuracy* (is the CARDS category right on the claims where it did). With about 140 to 400 cases per benchmark, differences of roughly four points are noise, so models within that range of each other are effectively tied.

| You want | Use | Exact category | Narrative-detection F1 | Notes |
| :------- | :-- | :------------- | :--------------------- | :---- |
| Lowest cost among the top group | `z-ai/glm-5.3-flash` | 0.628 | 0.864 | Statistically tied with the best on a balanced score (75% category accuracy, 25% false alarms); measured about $0.00009 per call, no failures; open weights under the MIT licence, but 320B total (18B active), so not for small hardware |
| Fastest | `google/gemma-4-31b-it` | 0.614 | 0.843 | Measured about $0.0004 per call and about 5 s per call, no failures; `mistralai/ministral-14b-2512` (0.598) is about as fast at about $0.0001 per call |
| Best category accuracy | `deepseek/deepseek-v4-flash` | 0.646 | 0.835 | Open weights (284B, 13B active), but a reasoning model: measured about $0.0017 per call (about 4 times gemma) and about 18 s per call, despite a catalog list price of $0.028 per million input tokens |
| Best at spotting narratives | `nvidia/nemotron-3-super-120b-a12b` | 0.612 | 0.865 | First of all models on narrative detection, about five times the price of deepseek-v4-flash |
| Best closed model | `qwen/qwen3.8-flash` | 0.637 | 0.859 | Needs `output_mode = "prompted"`, see the suite config |
| Best small model (14B) | `mistralai/ministral-14b-2512` | 0.598 | 0.830 | Best model under 15B; fits a 16 GB GPU (T4) or a 16 GB Mac at 4-bit |
| Best under 120B | `google/gemma-4-31b-it` | 0.614 | 0.843 | About $0.15 per million tokens and fast; `qwen3.6-35b` is better at detection (narrative F1 0.863) but slower, dearer and prone to token-limit failures |
| Best on a 32 GB Mac | `google/gemma-4-31b-it` | 0.614 | 0.843 | About 18 GB at 4-bit; `mistral-small-3.2-24b` (0.607, about 14 GB) leaves more headroom |
| Free, no API | transformer engine (`process` default) | 0.104 | 0.684 | Far behind every LLM on category accuracy; the matcher is behind as well (0.103, narrative F1 0.236) |

What the full results show:

- **Open weights match closed models.** The best open model beats or ties the best closed one on every score, and `gpt-4o-mini` ranks 15th of 32 (exact category 0.548).
- **Paying more does not help.** By catalog list price, the models at $0.30 per million tokens or more reach about 0.61, below the cheapest group (about 0.65). But list price is a poor guide: reasoning models cost far more per call than it suggests. Measured per call, `deepseek-v4-flash` (0.646) costs about $0.0017, `gemma-4-31b` (0.614) about $0.0004 and `ministral-14b-2512` (0.598) about $0.0001, so each extra point of accuracy over gemma costs several times as much.
- **Size matters below about 10B.** Under 10B the scores fall clearly (`qwen3.5-9b` 0.506, `llama-3.1-8b` 0.377). Between 14B and 35B the differences are within noise.
- **Mistral family.** `mistral-small-3.2-24b` (0.607) is effectively tied with `gemma-4-31b` and costs about the same hosted; it needs less memory (about 14 GB at 4-bit), so it suits 16 to 24 GB hardware, but its narrative detection is a little lower (F1 0.828 against 0.843). `ministral-14b-2512` (0.598) is the best small model. `mistral-small-2603` (0.497), `mistral-nemo` (0.431) and `mistral-large-2512` (0.422, with failed items) are not worth using.
- **Review context does not help on v2.** It lowered the balanced score for six of seven finalists (significantly for `glm-5.3-flash`, -0.064, and `ministral-14b-2512`, -0.075), mostly by adding false alarms, against gold labels that were annotated from the claim alone. Classify the claim alone.
- **Check the failure count.** A model that cannot follow the output format scores badly without the score saying why. In this run `ling-3.0-flash` answered "no narrative" for almost every claim and `mistral-large-2512` was rate-limited upstream (failed items count as wrong), so neither is a fair comparison. The report shows `n_failed` for every model.

Which prompt to use. All the results above use one prompt, the `xplainnlp-nslp` preset. We also compared it with the other two built-in prompts, `climatesense-nslp` and `cards-narrative`, on three models and all three benchmarks (claim only, same settings, no failed items):

| Model | Prompt | Exact category | Narrative-detection F1 | False alarms |
| :---- | :----- | :------------- | :--------------------- | :----------- |
| `gemma-4-31b` | `xplainnlp-nslp` (default) | 0.614 | 0.843 | 21.7% |
| | `climatesense-nslp` | 0.566 | 0.861 | 15.7% |
| | `cards-narrative` | 0.627 | 0.823 | 28.5% |
| `deepseek-v4-flash` | `xplainnlp-nslp` (default) | 0.646 | 0.835 | 22.5% |
| | `climatesense-nslp` | 0.611 | 0.858 | 14.9% |
| | `cards-narrative` | 0.644 | 0.795 | 32.4% |
| `ministral-14b-2512` | `xplainnlp-nslp` (default) | 0.598 | 0.830 | 18.6% |
| | `climatesense-nslp` | 0.513 | 0.840 | 17.7% |
| | `cards-narrative` | 0.560 | 0.701 | 54.5% |

No prompt beats the default by more than noise on exact category: `cards-narrative` is +1.3 points for gemma and -0.2 for deepseek, and clearly worse for ministral. `climatesense-nslp` is more cautious (detection F1 up about 2 points, false alarms down 6 to 8 points) but loses 3 to 5 points of exact category, and 8 or more for ministral. `cards-narrative` flags more claims, so false alarms rise. The prompt matters less than the model (the best and worst models differ by about 25 points), but a small model can be hurt badly by the wrong prompt. "False alarms" is the share of documents with no narrative (`0_0`) that were given a category. The default prompt over-flags about one in five of them, so prompt optimisation (`optimization.py`, GEPA) is most worth trying to cut false alarms while keeping category accuracy; it has not been run on these models, and to avoid overfitting it should be scored on data it was not trained on.

Prompt optimisation. `optimization.py` tunes the system prompt with GEPA, which proposes edits through a reflection model and scores them on training cases. We ran it once, on `google/gemma-4-31b-it` starting from the default prompt, with `deepseek/deepseek-v4-pro` as the reflection model, on a shuffled mix of ClimateSense v1/v2 (including the documents with no narrative) and the NSLP train split (300 training and 150 validation cases, a budget of 1,000 calls, about $0.3). `build_mixed_trainval(..., climate_only=False, shuffle_seed=...)` and `build_heldout(...)` exist for this: the ClimateSense files are not in random order (the first 150 cases of v1 are 97% no-narrative, the rest 40%), and the default of loading only documents that carry a category would teach a prompt to flag everything. The tuned prompt was then scored on cases the optimiser never saw (the rest of v1 and v2, and the NSLP test split):

| Model | Cases | Exact match before | after | Difference (95% interval) | False alarms before | after |
| :---- | :---- | :----------------- | :---- | :------------------------ | :------------------ | :---- |
| `gemma-4-31b` (the exact text the optimiser returned) | 547 | 0.746 | 0.784 | +3.8 points (+1.1 to +6.6, p = 0.009) | v1 7.7%, v2 53.4% | v1 3.2%, v2 25.9% |
| `gemma-4-31b` (same prompt, JSON wrapper removed) | 547 | 0.746 | 0.764 | +1.8 points (-0.7 to +4.4, p = 0.22) | v1 7.7%, v2 53.4% | v1 3.2%, v2 31.0% |
| `ministral-14b-2512` | 547 | 0.757 | 0.757 | 0.0 points | v1 7.7%, v2 34.5% | v1 4.5%, v2 24.1% |
| `deepseek-v4-flash` (v2 and NSLP test only) | 299 | 0.763 | 0.783 | +2.0 points (-1.7 to +5.7, p = 0.39) | v2 34.5% | v2 22.4% |

The tuned prompt reliably makes fewer false alarms, but it also misses more real narratives (detection recall on v2: gemma 0.897 to 0.776, deepseek 0.931 to 0.862) and the category accuracy on detected v2 claims falls, so it trades one kind of error for the other. The one significant gain belongs to one model and to the exact text with its JSON wrapper, which the optimiser returned (the optimiser's output is an `{"instruction": "..."}` object and the model was scored with it as given); with the wrapper removed the gain is not significant, and it did not carry over to ministral. The tuned prompt also contains examples from the annotated data, so it may be fitted to them. On the balanced score of [docs/model-selection.md](docs/model-selection.md) (75% category accuracy, 25% false alarms) it never helped across five models (gemma-4-31b, glm-5.3-flash, qwen3.8-flash, ministral-14b-2512, deepseek-v4-flash) and clearly hurt ministral-14b-2512, so use the default prompt. It is therefore available only as an opt-in preset, `xplainnlp-nslp-tuned` (for example `climafactskg process --classifier llm --preset xplainnlp-nslp-tuned ...`), whose docstring records these numbers; check it against the default on your own data with `eval run` before using it. The default preset is unchanged.

Classifying the whole graph (about 263,000 texts: 261,858 from ClimateSenseKG and 1,589 from Skeptical Science) with the gate on sends only the texts it passes to the model, about 8% or roughly 21,000 on the sample we checked. The per-call costs below were measured on 24 real claims each, as the change in the OpenRouter account's usage; the totals multiply them by the number of calls and are estimates, not a full run. Do not use the catalog list price to predict cost: calls are routed to providers that charge several times the cheapest list price (for deepseek-v4-flash, $0.03 to $0.44 per million input tokens and up to $1.66 output across providers) and reasoning tokens are billed, so deepseek-v4-flash cost about 28 times what its list price implied.

| Setup | Measured per call | Gate on (about 21,000 calls) | Gate off (about 263,000 calls) | Time, gate on |
| :---- | :---------------- | :--------------------------- | :----------------------------- | :------------ |
| `mistralai/ministral-14b-2512` hosted | about $0.0001 | about $2 | about $26 | about 2 hours |
| `google/gemma-4-31b-it` hosted, concurrency 24 | about $0.0004 | about $8 | about $100 | about 2 hours (about 5 s per call) |
| `deepseek/deepseek-v4-flash` hosted, concurrency 6 | about $0.0017 | about $36 | about $450 | about 18 hours (it reasons for about 18 s per call) |
| `gemma-4-31b` or `mistral-small-3.2-24b` on a Colab L4 with vLLM | Colab compute units | | | about 2 to 3 hours, not measured |

`mistral-small-3.2-24b` hosted was not measured: its usage was not booked in the test window, and its calls were slow (about 34 s median). With the gate off the same models cost about 12 times more and a reasoning model takes days, so the gate matters most when running hosted. At these prices running a small model yourself is worth considering for a full run.

For example, `climafactskg process --classifier llm --provider openrouter --model google/gemma-4-31b-it --preclassifier --concurrency 24` runs the whole graph on hosted gemma with the gate on (needs `OPENROUTER_API_KEY`, and the `transformer` extra for the gate; `--preset`, `--provider` and `--model` need `--classifier llm`). Each entry's `cards_category_classifier` field then records the preset and model, such as `xplainnlp-nslp|openrouter/google/gemma-4-31b-it`, so a later reader can tell which model produced the label (it is stored in the database, not yet emitted into the graph). A run is resumable: successful answers are cached and failed items are asked again next time. If you want to start now, `gemma-4-31b` hosted is the practical choice (best category accuracy under 120B, fast, no failures in the timing test); `deepseek-v4-flash` scores about 3 points higher and costs less, but is slow unless its reasoning effort is lowered. The ClimateSenseKG endpoint tags about 13,000 claims with `schema:mentions dbpedia:Climate_change`, which could pre-filter the query, but that silently drops every climate claim without that tag, and how many that is has not been measured, so the collector does not use it.

Running it yourself (sizes and memory arithmetic, not measured on this hardware; the scores are within noise of each other, so choose by memory and speed, and see [docs/model-selection.md](docs/model-selection.md#running-it-yourself)):

| Hardware | Memory | Model |
| :------- | :----- | :---- |
| T4 (Colab) | 16 GB | `ministral-14b-2512` at 4-bit (about 9 GB). The T4 has no bf16 and no FlashAttention 2, so use fp16 with an AWQ or GGUF model |
| L4 (Colab) | 24 GB | `gemma-4-31b` at 4-bit (about 18 GB), or `mistral-small-3.2-24b` (about 14 GB) for more room for context |
| A100 40 GB (Colab) | 40 GB | `gemma-4-31b` at 8-bit or `qwen3.6-35b` at 4-bit; `nemotron-3-super-120b` needs about 65 GB and does not fit |
| A100 80 GB or H100 (Colab) | 80 GB | `nemotron-3-super-120b` at 4-bit (about 65 GB, a tight fit; best balanced score of the locally runnable models, 0.630, but its speed was not measured) |
| Mac, 32 GB | 32 GB | `gemma-4-31b` or `mistral-small-3.2-24b` at 4-bit |
| Mac or GPU, 16 GB | 16 GB | `ministral-14b-2512` at 4-bit |
| 8 GB | 8 GB | Nothing good fits; `qwen3.5-9b` (0.506) is the best model under 10B, with a large drop in accuracy |

On a GPU, serve the model with vLLM or Ollama and let the classifier batch concurrent requests; on a Mac with LM Studio, send one request at a time. Both vLLM and Ollama expose an OpenAI-compatible API, so point the `ollama` or `lmstudio` provider's base URL at the server (this path is untested here). For the whole graph, hosted `google/gemma-4-31b-it` with the gate on is about $8 (see the measured costs above), `ministral-14b-2512` about $2, and `deepseek-v4-flash` about $36; compare that with the compute units a Colab session spends.

Caveats. The local figures (T4, Mac) are sizes and memory arithmetic: the scores were measured on hosted models, not on quantised local copies, and local speed was not benchmarked, so run a sample on your hardware before relying on it. Prices are the list prices OpenRouter showed at the time of the run and change. The ClimateBERT pre-classifier gate is off in the benchmarks. Measured on `climatesense_v1` (398 cases) with `deepseek-v4-flash`, `qwen3.8-flash` and `ministral-14b-2512`, turning it on removed about a third of the false alarms (precision up 3 to 6 points, `0_0` documents given a category down from 6 to 11% to 4 to 7%) but also dropped about 3.5 points of recall, because it sets aside about 3% of the claims that do carry a narrative (5 of 153). Narrative-detection F1 stayed within noise (-0.002 to +0.015), exact category fell by 2 to 2.6 points (that score covers only the claims that have a category), and category accuracy on detected claims did not change. On v2 and the NSLP test split it removes nothing. Its value is cost: on a sample of the graph's texts it set aside about 92% as not about climate, so it would cut the number of paid calls by about that share. `classify --classifier llm` and `process --classifier llm` both take `--no-preclassifier`; `process` also takes `--preclassifier` to turn it on, because the default preset (`xplainnlp-nslp`, the `qwen/qwen3-8b-mlx` model on a local LM Studio server) runs with the gate off.

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
