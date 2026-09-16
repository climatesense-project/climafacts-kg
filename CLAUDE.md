# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ClimaFactsKG builds an RDF knowledge graph linking climate-denial myths to scientific corrections, integrated with CimpleKG. It scrapes Skeptical Science, queries CimpleKG/ClimateSenseKG SPARQL endpoints, classifies claims against the CARDS misinformation taxonomy, and serves the result as `data/climafacts_kg.ttl` plus a live SPARQL endpoint.

## Commands

```bash
# Install (Poetry-managed; core install is lightweight, ML/eval deps are extras)
poetry install                                    # core: collect/build/serve/process --classifier llm
poetry install --extras transformer               # + process's default classifier (transformer, no API cost)
poetry install --extras "matcher transformer eval"  # + spaCy matcher, HF transformer classifier, eval/optimization pipeline
poetry install --all-extras

# Lint / format
ruff check .
ruff check --fix .
ruff format .

# Tests
pytest tests/
pytest tests/test_evaluators.py -v
pytest tests/test_matcher.py::TestCARDSMatcherClassify::test_unrelated_text_returns_default_code

# CLI (installed as `climafactskg` entrypoint -> climafactskg.cli:app)
climafactskg collect                                    # fetch raw data/URLs from all sources
climafactskg process --force --classifier transformer   # classify + populate intermediate SQLite DBs (transformer = default, free/local)
climafactskg process --classifier llm --concurrency 4   # same, via the LLM engine instead
climafactskg build                                      # assemble data/climafacts_kg.ttl from the DBs, auto-validates the output
climafactskg validate                                   # re-check an existing data/climafacts_kg.ttl parses and meets sanity thresholds
climafactskg classify "some claim text" --classifier matcher
climafactskg serve                                      # SPARQL endpoint over the built graph
climafactskg export
```

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, and `pytest tests/` on every push/PR to `main`.

Pre-commit hooks are configured (ruff format/check, toml/yaml checks, conventional-commit-msg linter) but only the `pre-commit` stage installs by default — run `pre-commit install --hook-type pre-commit --hook-type commit-msg` to also get commit-message linting locally.

## Architecture

Pipeline stages, each decoupled via a `preserve` SQLite DB as the boundary:

```
collectors/ (fetch + classify) -> preserve SQLite DBs -> builders/ (assemble RDF) -> data/climafacts_kg.ttl -> endpoints.py (serve)
```

- **collectors/** fetch raw data (`skepticalscience.py` scrapes SkS myth/rebuttal/glossary pages; `cimplekg.py`/`climatesensekg.py` query external SPARQL endpoints) *and* run CARDS classification inline via `collectors/utils.py:batch_classify_cards_category` before writing back to the DB. `cimplekg.py` and `climatesensekg.py` each have their own `fetch_claims`/`process_claims`/`classify_claims`/`process_all`, but the latter three are thin wrappers delegating to `collectors/utils.py`'s shared `process_claim_reviews`/`classify_claim_reviews`/`process_all_claim_reviews` — declared explicitly there as the contract any SPARQL ClaimReview source (`rev`/`date_published`/`text` columns) can reuse. A source whose SPARQL query can't produce that shape should write its own `process_claims` rather than forcing the fit.
- **classifiers/cards/** implements three interchangeable CARDS classifiers behind the same `classify`/`classify_batch` shape: `matcher.py` (spaCy + Jaccard similarity), `transformer.py` (two-stage HuggingFace: ClimateBERT binary gate + 18-class taxonomy model — the default engine for `process`, free/local, but needs the `transformer` extra since it imports torch/transformers directly — those imports raise a clear `ImportError` pointing at the extra if it's not installed), `llm/` (pydantic-ai structured output with per-provider presets, optional ClimateBERT pre-filter, `preserve` SQLite result cache — opt in via `--classifier llm`, core-installable). `pydantic-ai`/`openai` are core deps (not optional extras) since the LLM engine is a first-class alternative, not a fallback.
  - `batch_classify_cards_category` accepts a `cache_path` (Preserve SQLite file). Passing the *same* path for multiple sources — as `climafactskg process --cache-path` does by default (`data/cards_classification_cache.db`, shared across CimpleKG, ClimateSenseKG, and SkS arguments) — means identical claim/argument text is classified once, not once per source. `CARDSClassifier` (transformer) and `CARDSLLMClassifier` both cache through the shared `cache.py:ClassificationCache` (get-or-compute keyed by `hash(fingerprint|key)`, generic over the cached value via `serialize`/`deserialize` and over which computed values get written back via `should_cache` — the LLM classifier uses this to skip caching per-item failures). `CARDSLLMClassifier` holds two `ClassificationCache` instances (preclassifier gate, main LLM output); `CARDSMatcher` has no cache (cheap enough not to need one).
  - `classifiers/cards/base.py:CARDSClassifierBase` is the shared `classify(text, context=None)`/`classify_batch(texts, contexts=None)` interface all three engines implement — `context` is joined into the text (`f"{text}\n\n{context}"`) for matcher/transformer, or routed to a separate context-aware prompt template for the LLM engine.
  - `batch_classify_cards_category`'s `cards_category_classifier` provenance field means different things per engine: an LLM preset name (e.g. `"xplainnlp-nslp"`) for `classifier_engine="llm"`, or `TRANSFORMER_CLASSIFIER_ID` (`"transformer:<binary model>,<taxonomy model>"`) for `"transformer"`. Presence of this field — not its value — is what marks an entry as already-classified; switching a stored entry from one engine's tag to the other forces reclassification on the next run without `--force`.
  - `cards/__init__.py` lazily loads `CARDSMatcher`/`CARDSClassifier`/`CARDSEvalsAdapter`/`optimize_prompt` via `__getattr__` so that importing the LLM classifier alone does not pull in spaCy/transformers/torch/gepa. Preserve this when adding new classifier engines.
  - `classifier.py`'s `classify_batch` returns `None` (not a raised exception) for any item that still fails after retries, so a single bad item never discards the rest of a batch's successful results. `collectors/utils.py` relies on this: `None` categories are left un-written so the item stays pending for a future run. `transformer.py`'s `classify_batch` has no such per-item failure mode (mini-batched, but all-or-nothing per chunk).
  - Both engines compute a relatedness signal (`CARDSOutput.is_climate_related` for LLM, the binary-gate prediction for transformer) but discard it into a single collapsed `"0"`/`"0_0"` code — see the `project-relatedness-vs-category` memory note if working on eval/optimization accuracy.
  - `datasets.py`/`eval.py`/`evaluators.py` implement the eval pipeline against annotated ground truth: `nslp_dataset()` (HuggingFace ClimateCheck) and internal `climatesense_dataset_v1()`/`v2()` (Google Sheets/Drive annotations, reconciled via majority voting; annotators fill `cards_level1/2/3` as `"[5_1_1] Description"` — the bracket prefix is stripped by regex before voting, and depth-3 annotations are projected to depth-2 since the classifier only outputs depth-2).
  - `optimization.py` runs GEPA-based prompt auto-tuning; batch cases carry `(index, claim)` tuples (not bare claim text) so duplicate claim strings in one optimization batch don't collide on context lookup.
- **builders/** assemble the final RDF graph and are intentionally decoupled from collectors/classifiers — they only import `climafactskg.utils`, reading exclusively from the `preserve` DBs. `climafactskg.py` is the main graph builder (merges SkS arguments, `cards.ttl`, CimpleKG, and ClimateSenseKG mappings — the latter two share the same `generate_cimplekg_mappings()` function since they're produced by identical collector code); `sksreferenceskg.py` builds the scholarly-reference/citation subgraph.
- **parsers/skepticalscience.py** turns scraped HTML into structured fields consumed by the collector/builder. `climafactskg/utils.py`'s `parse_apa_citation_html` strips known cloud-storage presigned-URL credential params (`AWSAccessKeyId`, `X-Amz-*`, etc.) from extracted citation links — a real embedded AWS key was found in scraped data once, keep this when touching link extraction.
- `climafactskg validate` (and an automatic call at the end of `build`) parses the output graph and checks it's non-empty with at least one `sc:ClaimReview` node — catches build/serialization breakage (e.g. malformed Turtle from an unescaped literal) immediately rather than shipping a broken `.ttl`.
- Test coverage (`tests/`, 58 tests) covers the pure/stateless pieces: `taxonomy.py`, `evaluators.py`, `matcher.py`'s Jaccard math, `utils.py` (SPARQL parsing, citation detection), `stats.py`'s graph validity checks, `sksreferenceskg.py`'s private regex helpers. Collectors, builders' RDF-generation logic, and the LLM classifier's async/retry/cache internals remain untested; be extra careful with manual verification when touching those.

## Style

- Google-style docstrings (ruff `pydocstyle` convention), 120-char line length.
- Ruff handles both lint and format; run `ruff check --fix` before considering a change done.
- Prefer deferred/lazy imports for heavy optional dependencies (spaCy, transformers/torch, gepa) — see `cards/__init__.py` and `cli.py`'s per-command imports — so that commands not touching those paths stay fast and don't require the optional extras to be installed.
