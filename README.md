# 🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation

![Source code icense](https://img.shields.io/badge/Source_code_license-MIT-blue.svg?style=flat)
![ClimaFactsKG license](https://img.shields.io/badge/ClimaFactsKG_license-CC%20BY%204.0-success.svg?style=flat)
[![Publish ClimaFactsKG RDF](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml/badge.svg)](https://github.com/climatesense-project/climafacts-kg/actions/workflows/gh-pages-publish.yml)

> [ClimaFactsKG](https://purl.net/climafactskg/ns) is a knowledge graph designed to combat pervasive climate misinformation by linking 252 common climate myths with scientific corrections.
> ClimaFactsKG is integrated with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

Despite the overwhelming scientific evidence supporting the impact of humans on the environment, climate misinformation remains pervasive. This persistent spread of falsehoods is often achieved through the misrepresentation of scientific evidence and the promotion of pseudoscientific narratives that hinder effective climate action. To combat this issue, we introduce [ClimaFactsKG](https://purl.net/climafactskg/ns), a knowledge graph that links common climate change denial narratives with scientific corrections. ClimaFactsKG currently consists of 252 common climate myths and the corresponding scientific counter-arguments. A key feature of ClimaFactsKG is its strategic integration with [CimpleKG](https://github.com/CIMPLE-project/knowledge-base), one of the largest existing misinformation knowledge graphs. This connection allows the interlinking of scientific corrections and climate claims found in CimpleKG and significantly enhances the utility of ClimaFactsKG. By providing a structured and interlinked repository of climate change myths and their scientific rebuttals, ClimaFactsKG offers a valuable resource for researchers studying climate misinformation, fact-checkers seeking reliable counter-evidence, and educators aiming to improve climate literacy. 

## 🔍 Knowledge Graph Overview and Documentation

[ClimaFactsKG](https://purl.net/climafactskg/ns) uses [sc:ClaimReview](https://schema.org/ClaimReview) from the [Schema.org](https://schema.org/) vocabulary to represent claims and scientific corrections collected from the [Skeptical Science](https://skepticalscience.com/) website.
The categorisation of misinforming climate claims is based on the [CARDS](https://cardsclimate.com/) taxonomy. CARDS is used to connect sc:ClaimReview between ClimaFactsKG and [CimpleKG](https://github.com/CIMPLE-project/knowledge-base).

### 🔗 RDF Namespaces
The ClimaFactsKG namespace is: https://purl.net/climafactskg/ns#.

ClimaFactsKG commonly uses the following namespaces and prefixes:

| Prefix | URI                                     |
| ------ | --------------------------------------- |
|        | <https://purl.net/climafactskg/ns#>     |
| owl    | <http://www.w3.org/2002/07/owl#>        |
| rdfs   | <http://www.w3.org/2000/01/rdf-schema#> | 
| sc     | <https://schema.org/>                   |
| skos   | <http://www.w3.org/2004/02/skos/core#>  |


## 🚧 ClimaFactsKG Source Code
The source code of ClimaFactsKG is currently undergoing some updates and will be published soon here.

The data releases can be found on the [releases page](https://github.com/climatesense-project/climafacts-kg/releases). 

## ©️ Licenses
ClimaFactsKG source code is released under the [MIT license](https://opensource.org/license/mit), whereas the knowledge graph is released under the [Creative Commons Attribution 4.0 International (CC-BY 4.0) license](https://creativecommons.org/licenses/by/4.0/).
