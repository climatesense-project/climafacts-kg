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

With Poetry, from a checkout of this repository:

```bash
poetry install --extras "matcher transformer eval"   # or: --all-extras
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
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

`process` classifies with the local transformer engine by default (`--classifier transformer`, requires the `transformer` extra — see Installation above); pass `--classifier llm` to use the LLM-based path instead (core install, see provider table below). `build` merges SkepticalScience, CimpleKG, and ClimateSenseKG data plus the CARDS taxonomy into one `data/climafacts_kg.ttl`.

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
│ --cache-path       TEXT  Path to a Preserve SQLite cache file. LLM only.                                │
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
```

### 🧩 CARDS Classifiers (Python API)

The `climafactskg.classifiers.cards` module exposes three classifiers for programmatic use.

#### Transformer classifier (two-stage, default)

Uses a ClimateBERT-based binary relevance filter followed by a fine-tuned CARDS taxonomy model. No API key required.

```python
from climafactskg.classifiers.cards import CARDSClassifier

clf = CARDSClassifier()
clf.classify("Global warming stopped in 1998")  # → e.g. "1_0"
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
