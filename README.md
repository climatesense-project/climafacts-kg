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

No model is clearly the best: roughly the top ten LLMs are statistically tied, so the choice comes down to cost, speed, where you run it and which kind of mistake you can tolerate. All results use the default prompt on the claim alone (neither the tuned prompt nor review context helped).

| If you want | Take | Why |
| :---------- | :--- | :-- |
| Lowest cost among the top group | `glm-5.3-flash` | Balanced score 0.645 (third), about $0.00009 per call, no failures. Open weights, MIT licence, 320B total and 18B active parameters (model card), so hosted only for most people. |
| Highest balanced score | `qwen3.8-flash` | 0.654 (tied with `deepseek-v4-flash`), about $0.00033 per call; open weights not confirmed |
| Highest category accuracy | `deepseek-v4-flash` | 0.604 on documents with a narrative, but the most false alarms of the finalists (19.9%) and about $0.0017 per call |
| Fastest | `gemma-4-31b` or `ministral-14b-2512` | About 5 s per call; gemma has 19% false alarms, ministral 17% |
| Your own hardware (16 to 24 GB) | `ministral-14b-2512` (16 GB) or `gemma-4-31b` (24 GB or more) | Balanced 0.616 and 0.620, short answers so fast per call; see [Running it yourself](#running-it-yourself) |
| Smallest that still holds up | `ministral-14b-2512` | 14B, balanced 0.616, fits a 16 GB GPU or Mac at 4-bit |

For the whole graph, classify with the ClimateBERT gate on (`--preclassifier`), which sets aside about 92% of the texts as not about climate, for example `climafactskg process --classifier llm --provider openrouter --model z-ai/glm-5.3-flash --preclassifier`. The charts, measured costs, the prompt and gate experiments, hardware notes and caveats are in [docs/model-selection.md](docs/model-selection.md); how to run the benchmarks yourself is in [docs/evaluation.md](docs/evaluation.md).

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
