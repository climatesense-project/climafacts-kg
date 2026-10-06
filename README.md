# 🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation

![Source code license](https://img.shields.io/badge/Source_code_license-MIT-blue.svg?style=flat)
![ClimaFactsKG license](https://img.shields.io/badge/ClimaFactsKG_license-CC%20BY%204.0-success.svg?style=flat)
[![CI](https://github.com/climatesense-project/climafacts-kg/actions/workflows/ci.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/ci.yml)
[![Software Release](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml)
[![Data Release](https://github.com/climatesense-project/climafacts-kg/actions/workflows/data-release.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/data-release.yml)
[![Publish ClimaFactsKG RDF](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml)

> [ClimaFactsKG](https://purl.net/climatesense/climafactskg/ns) is a knowledge graph designed to combat climate misinformation by linking common climate myths across 28 languages with scientific corrections and peer-reviewed evidence. Integrated with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

ClimaFactsKG covers 253 unique climate myths (represented by 1,589 `sc:ClaimReview` entities across 28 languages) and links them to 1,205 peer-reviewed `sc:ScholarlyArticle` references collected from [Skeptical Science](https://skepticalscience.com/). Integration with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base) connects scientific corrections with widespread climate claims, providing a structured resource for researchers, fact-checkers, and educators.

## 🔍 Knowledge Graph Overview

ClimaFactsKG represents claims and scientific rebuttals using [`sc:ClaimReview`](https://schema.org/ClaimReview) from [Schema.org](https://schema.org/). Climate claims are categorised using the [CARDS](https://cardsclimate.com/) taxonomy, which also connects `sc:ClaimReview` entries between ClimaFactsKG and [CimpleKG](https://github.com/CIMPLE-project/knowledge-base) (see [docs/taxonomy.md](docs/taxonomy.md) for taxonomy definitions and assessment mappings). References cited in Skeptical Science rebuttals are modelled as structured `sc:ScholarlyArticle` nodes linked directly to the reviews that cite them.

### 🔗 RDF Namespaces

The ClimaFactsKG instance-data namespace is `https://purl.net/climatesense/climafactskg/ns#`.

The CARDS taxonomy uses its own namespace (`https://purl.net/climatesense/cards/ns#`) to maintain a shared identifier space (`cards:1_1`, `cards:2_3`, ...) across both ClimaFactsKG and CimpleKG.

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

Each CARDS label is linked to its review via `schema:about` (and reciprocal `schema:subjectOf`). Provenance for the classification model is recorded using `schema:AssessAction`:

| Entity | Mapping | Description |
| :----- | :------ | :---------- |
| Classification run | `:classification_<md5>` | `schema:AssessAction` representing the classification event |
| Model | `schema:instrument` `:model_<md5>` | `schema:SoftwareApplication` identifying the model used |
| Target review | `schema:object` | IRI of the classified `ClaimReview` |

```turtle
:classification_34368a354ffd368cd4848231b844379a
    a schema:AssessAction ;
    schema:name "CARDS labelling, two-stage transformer" ;
    schema:instrument :model_0393bb74e1266405570ef25d42565c6b, :model_34e9248425d7d6b866b21c111863e2c5 ;
    schema:object :claimreview_b9ba07b8af9a5410fdc5cb7be7acb708 .

:model_0393bb74e1266405570ef25d42565c6b a schema:SoftwareApplication ; schema:name "crarojasca/BinaryAugmentedCARDS" .
```

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

## 🖥️ Source Code and Installation

Knowledge graph datasets and release artifacts are available on the [releases page](https://github.com/climatesense-project/climafacts-kg/releases).

### 📦 Installation

Install directly from GitHub via `pip`:

```bash
# Core install (CLI, SPARQL server, and LLM classifier)
pip install "git+https://github.com/climatesense-project/climafacts-kg.git"
```

Or from a local clone:

```bash
git clone https://github.com/climatesense-project/climafacts-kg.git
cd climafacts-kg
pip install .
```

#### Optional Extras

Install additional classifiers or evaluation tooling via extras:

```bash
pip install "climafactskg[transformer] @ git+https://github.com/climatesense-project/climafacts-kg.git"  # Two-stage HuggingFace model & ClimateBERT gate
pip install "climafactskg[matcher] @ git+https://github.com/climatesense-project/climafacts-kg.git"      # Rule-based Jaccard similarity matcher (spaCy)
pip install "climafactskg[eval] @ git+https://github.com/climatesense-project/climafacts-kg.git"         # Benchmark evaluation pipeline (GEPA, pydantic-evals)
pip install "climafactskg[all] @ git+https://github.com/climatesense-project/climafacts-kg.git"          # All optional dependencies
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add "git+https://github.com/climatesense-project/climafacts-kg.git"
# Or from a local clone:
uv sync --all-extras
```

### ⌨️ Command Line Interface (CLI)

ClimaFactsKG provides a command-line interface via `climafactskg`:

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

#### Pipeline Workflow

1. **`collect`**: Gathers raw claims and debunkings from Skeptical Science, CimpleKG, and ClimateSenseKG.
2. **`process`**: Classifies claims using the CARDS taxonomy. Supports the local two-stage transformer (`--classifier transformer`, default, requires `[transformer]`) or LLM-based classification (`--classifier llm`). Results are cached in SQLite (`data/cards_classification_cache.db`).
3. **`build`**: Merges collected data, references, and taxonomy into `data/climafacts_kg.ttl`.
4. **`serve`**: Serves the knowledge graph over a local SPARQL endpoint (see [docs/sparql.md](docs/sparql.md) for query patterns).
5. **`validate`**: Validates Turtle syntax and RDF/XML serialisation.

Example running the full LLM classification pipeline:

```bash
climafactskg process --classifier llm --provider openrouter --model google/gemma-4-31b-it --preclassifier --concurrency 24
```

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

The `climafactskg.classifiers.cards` module provides three classifiers sharing a common interface (`classify(text, context=None)` and `classify_batch(texts, contexts=None)`):

* **`CARDSLLMClassifier`**: LLM-based classification with optional ClimateBERT pre-filtering.
* **`CARDSClassifier`**: Local two-stage transformer (ClimateBERT relevance filter + fine-tuned CARDS model).
* **`CARDSMatcher`**: Fast rule-based Jaccard similarity matcher.

#### Batch Classification

`classify_batch` supports optional fact-check context per claim (use `None` for claims without context). Results are cached by text and context:

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

#### Serving a classifier

```bash
climafactskg serve classifier --classifier llm --preset xplainnlp-nslp --port 8001
curl -s localhost:8001/classify -H 'content-type: application/json' -d '{"text": "CO2 is plant food"}'
curl -s localhost:8001/classify/batch -H 'content-type: application/json' -d '{"texts": ["a", "b"]}'
```

`POST /classify` takes `text` and optional `context`; `POST /classify/batch` takes `texts` (max 256) and optional `contexts`, and returns `null` for items that failed. `GET /healthz` reports status and OpenAPI docs live at `/docs`. It binds to `127.0.0.1`. Set `CLIMAFACTSKG_API_KEY` (comma-separated for several keys, so you can rotate without downtime) to require `Authorization: Bearer <key>` on the two classify routes; `/healthz` and `/docs` stay open. Unset means no authentication, and binding to a non-local host that way logs a warning. The key travels in clear over plain HTTP, so terminate TLS in a proxy before exposing the server.

#### LLM classifier

Structured-output LLM classifier built on [pydantic-ai](https://github.com/pydantic/pydantic-ai). Supports any OpenAI-compatible provider and includes an optional ClimateBERT pre-filter and [Preserve](https://github.com/kylepollina/preserve) SQLite result cache.

Supported providers:

| Provider string | Backend | Credentials |
| :-------------- | :------ | :---------- |
| `"openai"` | OpenAI API, or any OpenAI-compatible endpoint | `OPENAI_API_KEY` env var; set `OPENAI_BASE_URL` to use another endpoint |
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
print(registered_presets())  # → ('climatesense-nslp', 'xplainnlp-nslp', 'xplainnlp-nslp-tuned', 'xplainnlp-nslp-gemma-tuned', 'cards-narrative')

# Batch classification (concurrent LLM calls)
labels = clf.classify_batch(["text one", "text two", "text three"], concurrency=4)
```

**Built-in presets:**

| Preset name | Provider | Model |
| :---------- | :------- | :---- |
| `climatesense-nslp` | `openrouter` | `openai/gpt-5.2` |
| `xplainnlp-nslp` | `lmstudio` | `qwen/qwen3-8b-mlx` |
| `xplainnlp-nslp-tuned` | `lmstudio` | `qwen/qwen3-8b-mlx` (experimental: `xplainnlp-nslp` with a GEPA-tuned system prompt, see the results under "Which model to use") |
| `xplainnlp-nslp-gemma-tuned` | `lmstudio` | `qwen/qwen3-8b-mlx` (experimental: a prompt tuned for `google/gemma-4-31b-it`, +0.039 balanced score there; it is not meant for other models, see its docstring) |
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

### 🧭 Model Recommendations

Evaluation benchmarks indicate comparable performance across top-performing models, with the optimal choice depending on cost, inference latency, hardware availability, and error profile:

| Requirement | Recommended Model | Characteristics |
| :---------- | :---------------- | :-------------- |
| Lowest inference cost | `glm-5.3-flash` | Balanced score 0.645, ~\$0.0002 per call (measured on 200 gate-passed graph texts). MIT licence, MoE architecture (320B total / 18B active parameters). |
| Highest balanced score | `qwen3.8-flash` | Balanced score 0.654, ~\$0.00033 per call. |
| Highest category accuracy | `deepseek-v4-flash` | 0.604 category accuracy on narrative claims, 19.9% false-alarm rate, ~\$0.0017 per call. |
| Lowest latency | `gemma-4-31b` or `ministral-14b-2512` | ~5 s per call via hosted providers. |
| Local inference (16–24 GB VRAM) | `ministral-14b-2512` (16 GB) or `gemma-4-31b` (24 GB+) | Balanced score 0.616 / 0.620; see [docs/model-selection.md](docs/model-selection.md#running-it-yourself). |
| Compact local model | `ministral-14b-2512` | 14B parameters, balanced score 0.616; runs on 16 GB Apple Silicon / GPU at 4-bit quantisation. |

Enabling the ClimateBERT pre-classifier gate (`--preclassifier`) filters out approximately 92% of non-climate content prior to LLM inference, significantly lowering API token costs. Comprehensive benchmarks, measured costs, prompt experiments, and hardware guidance are detailed in [docs/model-selection.md](docs/model-selection.md); benchmarking procedures are described in [docs/evaluation.md](docs/evaluation.md).

## ©️ Licences

ClimaFactsKG source code is released under the [MIT licence](https://opensource.org/license/mit), whereas the knowledge graph is released under the [Creative Commons Attribution 4.0 International (CC-BY 4.0) licence](https://creativecommons.org/licenses/by/4.0/).

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
