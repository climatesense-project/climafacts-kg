# CARDS Taxonomy and Assessment Mappings

This document details the [CARDS](https://cardsclimate.com/) climate misinformation taxonomy used in ClimaFactsKG, its RDF representation, and how fact-check assessments and classifier provenance are modelled.

---

## 🗂️ The CARDS Taxonomy

CARDS (Computer-Assisted Recognition of Denial and Scepticism) categorises climate misinformation into five major denial claims, plus non-misinformation sentinels and hierarchical subcategories.

All concepts reside under the shared CARDS namespace:
`https://purl.net/climatesense/cards/ns#`

### 1. Top-Level Categories

| ID | URI | Category Name / Narrative |
| :-- | :-- | :------------------------ |
| `0` / `0_0` | `cards:0` / `cards:0_0` | Non-misinformation / Climate-related text with no denial narrative |
| `1` / `1_0` | `cards:1` / `cards:1_0` | Global warming is not happening |
| `2` / `2_0` | `cards:2` / `cards:2_0` | Human greenhouse gases are not causing global warming |
| `3` / `3_0` | `cards:3` / `cards:3_0` | Climate impacts are not bad |
| `4` / `4_0` | `cards:4` / `cards:4_0` | Climate solutions will not work |
| `5` / `5_0` | `cards:5` / `cards:5_0` | Climate movement and science are unreliable |

*(Note: `_0` suffixes serve as general parent-level classifications when a subcategory cannot be determined).*

---

### 2. Subcategories and Concepts

#### Category 1: Global Warming is Not Happening
* `1_1` — *Ice isn't melting* (`cards:1_1`)
  * `1_1_1`: Antarctica isn't melting
  * `1_1_2`: Greenland isn't melting
  * `1_1_3`: Arctic isn't melting
  * `1_1_4`: Glaciers aren't vanishing
* `1_2` — *Heading into ice age* (`cards:1_2`)
* `1_3` — *Weather is cold* (`cards:1_3`)
* `1_4` — *Hiatus in warming* (`cards:1_4`)
* `1_5` — *Oceans are cooling* (`cards:1_5`)
* `1_6` — *Sea level rise is exaggerated* (`cards:1_6`)
* `1_7` — *Extremes aren't increasing* (`cards:1_7`)
* `1_8` — *Changed the name* (`cards:1_8`)

#### Category 2: Human GHGs are Not Causing Global Warming
* `2_1` — *It's natural cycles* (`cards:2_1`)
  * `2_1_1`: It's the sun
  * `2_1_2`: It's geological
  * `2_1_3`: It's the ocean
  * `2_1_4`: Past climate change
  * `2_1_5`: Tiny CO2 emissions
* `2_2` — *Non-GHG forcings* (`cards:2_2`)
* `2_3` — *No evidence for greenhouse effect* (`cards:2_3`)
  * `2_3_1`: CO2 is trace gas
  * `2_3_2`: Greenhouse effect is saturated
  * `2_3_3`: CO2 lags climate
  * `2_3_4`: Water vapour
  * `2_3_5`: Tropospheric hot spot
  * `2_3_6`: CO2 high in past
* `2_4` — *CO2 not rising* (`cards:2_4`)
* `2_5` — *Emissions not raising CO2 levels* (`cards:2_5`)

#### Category 3: Climate Impacts are Not Bad
* `3_1` — *Sensitivity is low* (`cards:3_1`)
* `3_2` — *No species impact* (`cards:3_2`)
  * `3_2_1`: Species can adapt
  * `3_2_2`: Polar bears ok
  * `3_2_3`: Oceans are ok
* `3_3` — *Not a pollutant* (`cards:3_3`)
  * `3_3_1`: CO2 is plant food
* `3_4` — *Only a few degrees* (`cards:3_4`)
* `3_5` — *No link to conflict* (`cards:3_5`)
* `3_6` — *No health impacts* (`cards:3_6`)

#### Category 4: Climate Solutions Won't Work
* `4_1` — *Policies are harmful* (`cards:4_1`)
  * `4_1_1`: Policy increases costs
  * `4_1_2`: Policy weakens security
  * `4_1_3`: Policy harms environment
  * `4_1_4`: Rich future generations
  * `4_1_5`: Limits freedom
* `4_2` — *Policies are ineffective* (`cards:4_2`)
  * `4_2_1`: Green jobs don't work
  * `4_2_2`: Markets more efficient
  * `4_2_3`: Policy impact is negligible
  * `4_2_4`: One country is negligible
  * `4_2_5`: Better to adapt
  * `4_2_6`: China's emissions
  * `4_2_7`: Technological fix
* `4_3` — *Too hard* (`cards:4_3`)
  * `4_3_1`: Policy too difficult
  * `4_3_2`: Low public support
* `4_4` — *Clean energy won't work* (`cards:4_4`)
  * `4_4_1`: Clean energy unreliable
  * `4_4_2`: CCS is unproven
* `4_5` — *We need energy* (`cards:4_5`)
  * `4_5_1`: Fossil fuels are plentiful
  * `4_5_2`: Fossil fuels are cheap
  * `4_5_3`: Nuclear is good

#### Category 5: Climate Movement and Science are Unreliable
* `5_1` — *Science is unreliable* (`cards:5_1`)
  * `5_1_1`: No scientific consensus
  * `5_1_2`: Climate proxies are unreliable
  * `5_1_3`: Temperature records are unreliable
  * `5_1_4`: Climate models are unreliable
* `5_2` — *Movement is unreliable* (`cards:5_2`)
  * `5_2_1`: Climate is religion
  * `5_2_2`: Media is alarmist
  * `5_2_3`: Politicians are biased
  * `5_2_4`: Environmentalists are alarmist
  * `5_2_5`: Scientists are biased
* `5_3` — *Climate is conspiracy* (`cards:5_3`)
  * `5_3_1`: Climate policy is conspiracy
  * `5_3_2`: Climate science is conspiracy

---

## 🔗 RDF Modelling in ClimaFactsKG

### 1. Linking Claims to Taxonomy Concepts
Claims reviewed in ClimaFactsKG connect to CARDS concepts via reciprocal properties:

```turtle
@prefix cards: <https://purl.net/climatesense/cards/ns#> .
@prefix cf: <https://purl.net/climatesense/climafactskg/ns#> .
@prefix schema: <https://schema.org/> .

cf:claimreview_b9ba07b8af9a5410fdc5cb7be7acb708
    schema:about cards:2_1 ;
    schema:itemReviewed cf:claim_d41d8cd98f00b204e9800998ecf8427e .

cards:2_1
    schema:subjectOf cf:claimreview_b9ba07b8af9a5410fdc5cb7be7acb708 .
```

*(Entries classified as non-misinformation sentinels `0` or `0_0` do not receive `schema:about` links).*

---

### 2. Fact-Check Assessments and Ratings

Each myth debunking in Skeptical Science includes a structured rating assessment attached to the [`schema:ClaimReview`](https://schema.org/ClaimReview):

```turtle
cf:claimreview_b9ba07b8af9a5410fdc5cb7be7acb708
    schema:reviewRating _:b_rating .

_:b_rating
    a schema:Rating ;
    schema:name "False" ;
    schema:ratingValue 0 ;
    schema:bestRating 1 ;
    schema:worstRating 0 ;
    schema:ratingExplanation "Direct measurements demonstrate that greenhouse gases are driving observed warming."@en .
```

---

### 3. Classification Provenance (`schema:AssessAction`)

When automated models classify claims, provenance is captured using [`schema:AssessAction`](https://schema.org/AssessAction):

```turtle
cf:classification_34368a354ffd368cd4848231b844379a
    a schema:AssessAction ;
    schema:name "CARDS labelling, two-stage transformer" ;
    schema:instrument cf:model_0393bb74e1266405570ef25d42565c6b, cf:model_34e9248425d7d6b866b21c111863e2c5 ;
    schema:object cf:claimreview_b9ba07b8af9a5410fdc5cb7be7acb708 .

cf:model_0393bb74e1266405570ef25d42565c6b
    a schema:SoftwareApplication ;
    schema:name "crarojasca/BinaryAugmentedCARDS" .
```
