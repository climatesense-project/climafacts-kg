# Querying ClimaFactsKG with SPARQL

This guide provides practical SPARQL queries for interrogating the ClimaFactsKG knowledge graph.

---

## 🚀 Running the Local SPARQL Server

You can launch a local SPARQL server serving `data/climafacts_kg.ttl`:

```bash
climafactskg serve --rdf data/climafacts_kg.ttl --port 8000
```

Once running, navigate to `http://localhost:8000` for an interactive SPARQL web interface, or submit `POST`/`GET` requests directly to `http://localhost:8000/`.

---

## 🔗 Common Prefixes

All examples below assume the following namespace declarations:

```sparql
PREFIX cf:     <https://purl.net/climatesense/climafactskg/ns#>
PREFIX cards:  <https://purl.net/climatesense/cards/ns#>
PREFIX schema: <https://schema.org/>
PREFIX cito:   <http://purl.org/spar/cito/>
PREFIX bibo:   <http://purl.org/ontology/bibo/>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
```

---

## 📋 Example Queries

### 1. Retrieve Climate Myths and Scientific Corrections
Finds reviewed myths alongside their titles and scientific explanations:

```sparql
SELECT ?review ?mythText ?scienceSummary WHERE {
  ?review a schema:ClaimReview ;
          schema:inLanguage "English" ;
          schema:claimReviewed ?claim ;
          schema:reviewRating ?rating .

  ?claim a schema:Claim ;
         schema:text ?mythText .

  ?rating a schema:Rating ;
          schema:ratingExplanation ?scienceSummary .
}
LIMIT 20
```

---

### 2. Retrieve Assessment and Rating Details
Inspects the structured ratings (`schema:Rating`) associated with claim reviews:

```sparql
SELECT ?review ?ratingValue ?ratingName ?explanation WHERE {
  ?review a schema:ClaimReview ;
          schema:reviewRating ?rating .

  ?rating a schema:Rating ;
          schema:ratingValue ?ratingValue ;
          schema:name ?ratingName ;
          schema:ratingExplanation ?explanation .
}
LIMIT 10
```

---

### 3. Retrieve Cited Scholarly Articles for a Myth
Finds peer-reviewed scientific references linked to claim reviews via `cito:cites`:

```sparql
SELECT ?review ?articleTitle ?year ?doi WHERE {
  ?review a schema:ClaimReview ;
          cito:cites ?article .

  ?article a schema:ScholarlyArticle ;
           schema:name ?articleTitle ;
           schema:datePublished ?year .

  OPTIONAL { ?article bibo:doi ?doi }
}
LIMIT 20
```

---

### 4. Query Claims by CARDS Misinformation Category
Finds all reviews classified under CARDS category `cards:2_1` (*Natural Cycles*):

```sparql
SELECT ?review ?mythTitle ?url WHERE {
  ?review a schema:ClaimReview ;
          schema:about cards:2_1 ;
          schema:name ?mythTitle ;
          schema:url ?url .
}
```

---

### 5. Count Claims Across CARDS Categories
Aggregates the number of claim reviews mapped to each CARDS category:

```sparql
SELECT ?category (COUNT(?review) AS ?claimCount) WHERE {
  ?review a schema:ClaimReview ;
          schema:about ?category .
}
GROUP BY ?category
ORDER BY DESC(?claimCount)
```

---

### 6. Query Classification Provenance and Machine Learning Models
Finds which automated model classified specific reviews using `schema:AssessAction`:

```sparql
SELECT ?action ?modelName ?review WHERE {
  ?action a schema:AssessAction ;
          schema:instrument ?model ;
          schema:object ?review .

  ?model a schema:SoftwareApplication ;
         schema:name ?modelName .
}
LIMIT 20
```

---

### 7. Count Myths by Language
Summarises the multilingual coverage of claim reviews in the graph:

```sparql
SELECT ?language (COUNT(?review) AS ?count) WHERE {
  ?review a schema:ClaimReview ;
          schema:inLanguage ?language .
}
GROUP BY ?language
ORDER BY DESC(?count)
```

---

## 🐍 Querying Programmatically in Python

### Using `rdflib` Directly

```python
from rdflib import Graph

g = Graph()
g.parse("data/climafacts_kg.ttl", format="turtle")

query = """
PREFIX schema: <https://schema.org/>
SELECT ?myth (COUNT(?ref) AS ?citedArticles) WHERE {
  ?review a schema:ClaimReview ;
          schema:name ?myth ;
          <http://purl.org/spar/cito/cites> ?ref .
}
GROUP BY ?myth
ORDER BY DESC(?citedArticles)
LIMIT 5
"""

for row in g.query(query):
    print(f"{row.myth}: {row.citedArticles} citations")
```
