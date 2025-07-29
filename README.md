# 🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation

![Source code icense](https://img.shields.io/badge/Source_code_license-MIT-blue.svg?style=flat)

![ClimaFactsKG license](https://img.shields.io/badge/ClimaFactsKG_license-CC%20BY%204.0-success.svg?style=flat)

[![Create Release](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/semantic-release.yml)
[![Publish ClimaFactsKG RDF](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml)

> [ClimaFactsKG](https://purl.net/climafactskg/ns) is a knowledge graph designed to combat pervasive climate misinformation by linking 252 common climate myths with scientific corrections.
> ClimaFactsKG is integrated with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

Despite the overwhelming scientific evidence supporting the impact of humans on the environment, climate misinformation remains pervasive. This persistent spread of falsehoods is often achieved through the misrepresentation of scientific evidence and the promotion of pseudoscientific narratives that hinder effective climate action. To combat this issue, we introduce [ClimaFactsKG](https://purl.net/climafactskg/ns), a knowledge graph that links common climate change denial narratives with scientific corrections. ClimaFactsKG currently consists of 252 common climate myths and the corresponding scientific counter-arguments. A key feature of ClimaFactsKG is its strategic integration with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base), one of the largest existing misinformation knowledge graphs. This connection allows the interlinking of scientific corrections and climate claims found in CimpleKG and significantly enhances the utility of ClimaFactsKG. By providing a structured and interlinked repository of climate change myths and their scientific rebuttals, ClimaFactsKG offers a valuable resource for researchers studying climate misinformation, fact-checkers seeking reliable counter-evidence, and educators aiming to improve climate literacy.

## 🔍 Knowledge Graph Overview and Documentation

[ClimaFactsKG](https://purl.net/climafactskg/ns) uses [ `sc:ClaimReview` ](https://schema.org/ClaimReview) from the [Schema.org](https://schema.org/) vocabulary to represent claims and scientific corrections collected from the [Skeptical Science](https://skepticalscience.com/) website.
The categorisation of misinforming climate claims is based on the [CARDS](https://cardsclimate.com/) taxonomy. CARDS is used to connect `sc:ClaimReview` between ClimaFactsKG and [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

### 🔗 RDF Namespaces

The ClimaFactsKG namespace is: https://purl.net/climafactskg/ns#.

ClimaFactsKG commonly uses the following namespaces and prefixes:

| Prefix   | URI                                     |
| :------- | :-------------------------------------- |
|          | <https://purl.net/climafactskg/ns#>     |
| `owl` | <http://www.w3.org/2002/07/owl#>        |
| `rdfs` | <http://www.w3.org/2000/01/rdf-schema#> |
| `sc` | <https://schema.org/>                   |
| `skos` | <http://www.w3.org/2004/02/skos/core#>  |

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
| *Related Argument*             | →     | `seeAlso` | <https://skepticalscience.com/global-cooling-january-2007-to-january-2008.htm>                                       |
| *source: (...)*                | →     | `sc:citation` | <https://wattsupwiththat.wordpress.com/2008/02/19/january-2008-4-sources-say-globally-cooler-in-the-past-12-months/> |

## 🖥️ ClimaFactsKG Source Code

The data and source code releases can be found on the [releases page](https://github.com/climatesense-project/climafacts-kg/releases).

### ⌨️ Command Line Interface (CLI)

ClimaFactsKG has a simple CLI interface that be accessed using the `climafactskg` command. The command line interface can be used for serving ClimaFactsKG (after [downloading](https://purl.archive.org/climafactskg/ns) or generating the RDF file).

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
│ classify   Classify text using CARDS.                                                                    │
│ serve      Create a SPARQL endpoint for serving a knowledge graph.                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## ©️ Licenses

ClimaFactsKG source code is released under the [MIT license](https://opensource.org/license/mit), whereas the knowledge graph is released under the [Creative Commons Attribution 4.0 International (CC-BY 4.0) license](https://creativecommons.org/licenses/by/4.0/).
