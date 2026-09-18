# CHANGELOG

<!-- version list -->

## v2.1.2 (2026-09-18)

### Bug Fixes

- **ci**: Add missing <!-- version list --> insertion marker to CHANGELOG.md
  ([`7c7642e`](https://github.com/climatesense-project/climafacts-kg/commit/7c7642e4f85e66aa5edacd3c90ff6c7089038676))

### Continuous Integration

- Add debug verbosity to semantic-release version, prior fix unconfirmed
  ([`56c635e`](https://github.com/climatesense-project/climafacts-kg/commit/56c635ea736c611babd5f9a50cbf315ff0aed76b))


## Unreleased

### Continuous Integration

- Add debug verbosity to semantic-release version, prior fix unconfirmed
  ([`56c635e`](https://github.com/climatesense-project/climafacts-kg/commit/56c635ea736c611babd5f9a50cbf315ff0aed76b))


## v2.1.1 (2026-09-18)

### Bug Fixes

- **ci**: Fetch tags before semantic-release version, not after
  ([`587cb62`](https://github.com/climatesense-project/climafacts-kg/commit/587cb62d808023f4af6d32e7d7d3abed16d82517))

### Documentation

- Backfill CHANGELOG.md missing history since v1.1.0
  ([`7c6dffa`](https://github.com/climatesense-project/climafacts-kg/commit/7c6dffa14373235f341e3a4cd6af952a7e15160f))


## Unreleased

### Bug Fixes

- Three issues from architecture review
  ([`dff52c1`](https://github.com/climatesense-project/climafacts-kg/commit/dff52c185f3950130c775baeb449802fe0286ef3))

- builders/climafactskg.py: cards_category exclusion only checked "0_0" (LLM engine's not-related
  sentinel), not "0" (transformer/ matcher's) — so transformer-classified SkS arguments (the default
  process engine) got a bogus SDO.about link to the "not relevant" CARDS taxonomy node.
  builders/cimplekg.py already excluded both correctly; climafactskg.py now matches it. - utils.py:
  fetch_url_content's cache_dir/cache_expiry defaults were os.getenv()/timedelta() calls evaluated
  once at import time, so env var changes after import (or before load_dotenv() runs) were silently
  ignored. Now read inside the function body, matching query_sparqlendpoint's existing correct
  pattern. - endpoints.py: serve_endpoint's own default host was "0.0.0.0" (network-exposed); the
  CLI wraps it with a safer 127.0.0.1 default but calling it directly (script, notebook, test) got
  no such protection. Default now matches the CLI.

### Documentation

- Replace two stale TODOs with concrete investigated findings
  ([`5e33077`](https://github.com/climatesense-project/climafacts-kg/commit/5e33077c6b5851f4ac7855a26184b195c172a1cc))

climatesensekg.py: checked the live endpoint's schema for a climate-relatedness pre-filter.
  schema:mentions dbpedia:Climate_change exists on ~13k ClaimReviews and could filter the query, but
  decided against it — permanent, silent recall loss for any climate claim not tagged with that
  exact entity, with no way to detect the exclusion later. Classifying everything costs more but has
  no recall risk.

builders/climafactskg.py: the "cross ref definitions and citations" TODO was half done and half
  vague. Citations are already implemented (sksreferenceskg.py:generate_citations_graph).
  Definitions (glossary terms discarded by parse_skstiptionary_references' citation=="4" filter) are
  not — documented the concrete remaining scope (parser, storage, RDF schema choice, builder
  function) instead of a one-line TODO, since it's comparable in size to the citations feature
  itself.

- **classifiers**: Fill gaps left by cache/interface unification
  ([`f483485`](https://github.com/climatesense-project/climafacts-kg/commit/f4834855d2cbdb4d98e8734ba56ec3c07ed7c3fe))

- Rewrite classify_batch's stale docstring (still described the old manual batch-read/write steps,
  not the current ClassificationCache delegation). - Document the shared cache_path,
  CARDSClassifierBase, and per-engine context support in README (was CLAUDE.md-only). - Add
  --context to the CLI's classify command (all three engines accept it now) and let --cache-path
  apply to the transformer engine too, not just LLM. - Add tests: matcher context joining/batch
  behavior, cache_path forwarding from batch_classify_cards_category to both engines.

### Features

- **collectors**: Persist is_climate_related instead of collapsing it
  ([`19876bc`](https://github.com/climatesense-project/climafacts-kg/commit/19876bc794ded5805a822610c112d0e58c92b113))

Both engines already compute a relatedness signal internally (LLM's CARDSOutput.is_climate_related,
  transformer's binary-gate result) but discarded it into the "0"/"0_0" category sentinel with no
  separate trace. Derive and store is_climate_related on every classified entry in
  batch_classify_cards_category, uniformly across engines (category not in NOT_RELATED_CATEGORIES),
  with zero classifier interface changes. One LLM-only edge case (is_climate_related=True,
  cards_category=None) stays unrecoverable at this level — documented in llm/classifier.py's
  docstring and the relatedness-vs-category memory note rather than solved via a return-type break.

- **utils**: Cache SPARQL query results (disk + in-process)
  ([`66902c1`](https://github.com/climatesense-project/climafacts-kg/commit/66902c1a539ea247ca8069bdfd6d5e23db648f6e))

collect() and process() each call fetch_claims() independently, so a normal collect-then-process run
  re-downloaded the same ~260k+137k row SPARQL result sets twice with no caching at all — a standing
  TODO in both collectors.

query_sparqlendpoint now caches to disk (keyed by endpoint+query, default 12h expiry via
  CLIMAFACTSKG_SPARQL_CACHE_EXPIRY — these endpoints refresh roughly daily) so repeat calls across
  separate CLI invocations reuse the last fetch instead of re-downloading. Also wrapped in lru_cache
  for free zero-I/O reuse within a single process.

Removes the now-stale "TODO Cache query results" comments from both collectors. Adds
  cache-hit/cache-expiry tests; existing tests updated to use per-test cache_dir so they don't
  collide with each other now that results are cached.

### Performance Improvements

- **classifiers**: Share CARDS classification cache across sources
  ([`a512dd1`](https://github.com/climatesense-project/climafacts-kg/commit/a512dd1799f1ee36b749130437b7027e16aefc5a))

CimpleKG and ClimateSenseKG independently classified identical claim text since each collector built
  its own classifier with no cache. Add cache.py:ClassificationCache (shared get-or-compute over a
  Preserve SQLite file) used by both CARDSClassifier (transformer, new cache_path support) and
  CARDSLLMClassifier (retrofit of its existing preclassifier/output caches onto the shared helper,
  cache key bytes unchanged so existing cache files stay valid). Thread cache_path through
  collectors/utils.py and the CLI's `process --cache-path` (default: one shared file across all
  sources) so identical text is classified once, not once per source.

### Refactoring

- Centralize logging config, remove it from library modules
  ([`45cfaa9`](https://github.com/climatesense-project/climafacts-kg/commit/45cfaa9160c20ff6b1b364442e7b73dc76c40f32))

Six library modules (builders/climafactskg.py, builders/cimplekg.py, builders/sksreferenceskg.py,
  collectors/cimplekg.py, collectors/climatesensekg.py, collectors/skepticalscience.py) each called
  logging.basicConfig(level=logging.INFO) at import time. Since basicConfig() no-ops once the root
  logger already has a handler, only whichever of these six happened to import first actually took
  effect — an accidental, import-order-dependent result, and a library anti-pattern regardless (it
  forces logging config on anyone embedding climafactskg as a library, not just the CLI). Moved the
  one call that matters to cli.py's module top level, the actual application entry point; library
  modules keep only logging.getLogger(__name__). optimization.py/eval.py's own basicConfig calls are
  untouched — both already properly guarded inside `if __name__ == "__main__":` blocks.

- Logger.* over bare logging.*, extract shared new_graph helper
  ([`eb2c94d`](https://github.com/climatesense-project/climafacts-kg/commit/eb2c94d685c420c5941627e63261c2563105f5c3))

- collectors/skepticalscience.py and all three builders/*.py called the root logger directly
  (logging.info/error/warning) instead of a module logger — inconsistent with every other module,
  and it makes log output impossible to filter/attribute by source module. Add logger =
  logging.getLogger(__name__) to each and switch all calls. - Extract
  builders/utils.py:new_graph(bindings) — the Graph()+NamespaceManager(Graph())+bind() sequence was
  repeated identically (aside from which prefixes) across builders/climafactskg.py, cimplekg.py, and
  sksreferenceskg.py. One helper, three call sites.

- Remove legacy/dead code
  ([`d372b58`](https://github.com/climatesense-project/climafacts-kg/commit/d372b586342522fafb12012f8adf7db946eb2289))

- Remove cards_classification() (transformer.py) — unused, untested, explicitly marked "legacy
  single-use helper"; CARDSClassifier is the maintained path. Drop it from __init__.py's lazy-load
  registry and __all__/docstring. - Remove deserialize_datetime() (utils.py) — no caller anywhere;
  serialize_datetime (its used counterpart) is untouched. - Remove bib["title"] duplicate field in
  parse_skstiptionary_references (parsers/skepticalscience.py) — same value as bib["header"],
  explicitly marked "kept for backward compatibility". Update its one reader
  (sksreferenceskg.py:generate_references_graph) to use "header" directly, and the function's
  docstring. - Drop a dead duplicate docstring statement in remove_html_tags.

- **builders**: Extract shared add_cards_category_link helper
  ([`3f335e5`](https://github.com/climatesense-project/climafacts-kg/commit/3f335e5a1b92042824ba4bf5f280e1ddaf4e8046))

builders/climafactskg.py and builders/cimplekg.py each hand-rolled the same SDO.about/SDO.subjectOf
  triple-adding logic with its own not-related-sentinel exclusion check inline — exactly the
  duplication that let the two drift out of sync (the "0" exclusion bug fixed earlier this session).
  Extract one add_cards_category_link(g, cards_ns, subject, cards_category) in cimplekg.py, used by
  both builders, so the exclusion list (NOT_RELATED_CARDS_CATEGORIES) has one home instead of two
  copies.

- **builders**: Extract shared safe_uriref, dedupe percent-encoding
  ([`ae11fa5`](https://github.com/climatesense-project/climafacts-kg/commit/ae11fa5467991ddd2c1d13521e53a52a67b62d06))

climafactskg.py's _safe_uriref (percent-encode a URL for a safe IRI) had its exact safe-char set
  (":/?#[]@!\$&'()*+,;=-._~%") duplicated inline in sksreferenceskg.py's reference-URL triple,
  rather than reused. Moved to builders/utils.py as safe_uriref, used by both. sksreferenceskg.py's
  DOI-specific quote() call (different safe set, slash-critical) is untouched — not the same case.

- **classifiers**: Unify CARDS classifier interface
  ([`284d6cd`](https://github.com/climatesense-project/climafacts-kg/commit/284d6cd0d1147de49113ce600f0502cc825d2e1a))

CARDSMatcher, CARDSClassifier (transformer), and CARDSLLMClassifier did the same job with drifting
  signatures — only the LLM engine accepted context. Add base.py:CARDSClassifierBase (ABC:
  classify(text, context=None), classify_batch(texts, contexts=None)) and have all three inherit it.
  Matcher and transformer gain real context support (joined into the text, matching
  ClimateBertClassifier's existing convention); the LLM engine already matched the shape. eval.py's
  evaluate()/benchmark_configs() context gate now checks isinstance(classifier, CARDSClassifierBase)
  instead of a private LLM-only attribute, so matcher/transformer now actually receive dataset
  context during evaluation instead of silently dropping it.

- **cli**: Route _validate_graph output through logger, not typer.echo
  ([`198f322`](https://github.com/climatesense-project/climafacts-kg/commit/198f322e5dc861ff7722ce86749fbb2c7b053c09))

Was a deliberate stdout/stderr split (typer.echo for CLI-command output, logger for progress) — user
  asked for consistency with the rest of the pipeline over script-parseable stdout, so switched all
  of it (stats, OK, FAILED) to logger.info/logger.error.

- **collectors**: Declare a shared claim-review pipeline instead of implicit reuse
  ([`eed3d7a`](https://github.com/climatesense-project/climafacts-kg/commit/eed3d7a3dde2ec0aafbb2a1793d6046a5d611752))

climatesensekg.py imported process_all directly from cimplekg.py — no wrapper, no declared contract,
  working only because both SPARQL queries happen to alias columns identically
  (rev/date_published/text). A future source with a different shape would have silently broken or
  written wrong data.

Moves the generic (non-source-specific) logic into collectors/utils.py as
  process_claim_reviews/classify_claim_reviews/process_all_claim_reviews, documented as the explicit
  contract any SPARQL ClaimReview source can reuse. cimplekg.py and climatesensekg.py each keep
  their own fetch_claims (source-specific) plus thin, documented wrapper functions delegating to the
  shared pipeline — no more accidental cross-module dependency, and cli.py's call sites are
  unchanged.

Adds tests/test_collectors_utils.py covering the shared pipeline directly.

- **llm**: Derive _TAXONOMY_CODE_SET from TaxonomyCode via get_args
  ([`b50d3a1`](https://github.com/climatesense-project/climafacts-kg/commit/b50d3a1f72b4ad2fd0c3fc7e8f24685a571f22f0))

_TAXONOMY_CODE_SET hand-retyped every member of the TaxonomyCode Literal right above it, with a
  comment admitting "must stay in sync with the Literal above" — the classic sign of a duplicate
  nobody wants to touch. typing.get_args() extracts a Literal's members at runtime, so the set can
  be derived instead of duplicated; the two can no longer drift out of sync by construction.


## v2.0.2 (2026-09-16)

### Bug Fixes

- **cli**: Isolate collect() steps so one failure doesn't skip the rest
  ([`2a4be6e`](https://github.com/climatesense-project/climafacts-kg/commit/2a4be6e073119e1540088372625569e9d790a03e))

collect() ran its 5 fetch calls as a flat sequence — a live 504 from CimpleKG's SPARQL endpoint once
  took the whole command down, skipping the unrelated ClimateSenseKG/SkepticalScience steps after
  it. process() already had this fix; collect() didn't.

Wraps each step in try/except, logging and continuing on failure, same pattern as process(). Adds
  tests/test_cli_collect.py covering both the happy path and the isolation behavior.


## v2.0.1 (2026-09-16)

### Bug Fixes

- **ci**: Don't double-nest gh-pages output under climafacts-kg/
  ([`00ca29b`](https://github.com/climatesense-project/climafacts-kg/commit/00ca29b81b96e651b6d366aca24eac8f4d888493))

This is a standard GitHub Project Pages site (no CNAME/custom domain), already served at
  https://climatesense-project.github.io/climafacts-kg/ by GitHub's own routing. Adding another
  climafacts-kg/ subfolder inside the published artifact double-nested every file path and left the
  actual site root without an index.html, causing a 404 there.


## v2.0.0 (2026-09-16)

### Continuous Integration

- Nest gh-pages output under climafacts-kg/ to avoid path collisions
  ([`80443b8`](https://github.com/climatesense-project/climafacts-kg/commit/80443b8af76f5219ac4c4156fcfeb25f9c5af808))

Published files now live at climafacts-kg/<file> instead of the Pages root, so this repo's output
  can't collide with another repo's files on a shared org-level Pages site or custom domain.

### Features

- **rdf**: Split CARDS taxonomy into its own namespace
  ([`0f8198f`](https://github.com/climatesense-project/climafacts-kg/commit/0f8198fcf107e1def2bd021f8fc53f50a30a914f))

CARDS concept URIs move from https://purl.net/climatesense/climafactskg/ns# to their own
  https://purl.net/climatesense/cards/ns#. CARDS is a shared taxonomy also used to connect claims in
  CimpleKG, not something owned by ClimaFactsKG, so it shouldn't be nested inside ClimaFactsKG's own
  namespace.

Updates data/cards.ttl, the taxonomy.py metadata, matcher.py's custom-taxonomy SPARQL query, both
  RDF builders (cimplekg.py, climafactskg.py), the SPARQL endpoint's prefix bindings, and publishes
  cards.ttl/cards.rdf as their own release assets and GH Pages files so the new namespace has
  somewhere to 303-redirect to.

BREAKING CHANGE: any external reference to a CARDS concept under the old
  https://purl.net/climatesense/climafactskg/ns#<code> URI now resolves under
  https://purl.net/climatesense/cards/ns#<code> instead. Instance-data URIs (ClaimReview,
  ScholarlyArticle, etc.) are unaffected.

### Breaking Changes

- **rdf**: Any external reference to a CARDS concept under the old
  https://purl.net/climatesense/climafactskg/ns#<code> URI now resolves under
  https://purl.net/climatesense/cards/ns#<code> instead. Instance-data URIs (ClaimReview,
  ScholarlyArticle, etc.) are unaffected.


## v1.6.0 (2026-09-16)

### Bug Fixes

- **build**: Make blank node ids deterministic for reproducible builds
  ([`63e5e0e`](https://github.com/climatesense-project/climafacts-kg/commit/63e5e0e2847ca06f7f31d600a490e85a7dabb38a))

BNode() with no explicit value gets a random id from rdflib each run, which made the Turtle
  serializer's ordering of multi-valued properties (e.g. multiple sc:author entries per reference)
  shuffle on every build even with unchanged source data, producing large spurious diffs.

Derive rating/author/DOI-identifier BNode ids from content (hash_string over article/claim id +
  position) instead. As a side effect, this also deduplicates author/DOI nodes that were
  content-identical but previously always got distinct random ids and could never merge.

- **pipeline**: Fix classification/build bugs, add classifier engine selection, CI, tests, docs
  ([`c48d66f`](https://github.com/climatesense-project/climafacts-kg/commit/c48d66f7c23bb00753e1ad927085247a177fd47b))

Fixes: preset concurrency/preclassifier overrides ignored, batch classification losing all results
  on one item's failure, semaphore held during retry backoff, stale non-English categories never
  cleared, short citation fragments dropped, SPARQL parser crashing on malformed response, GEPA
  context lookup colliding on duplicate claim text, eager heavy imports on classifier package load,
  leaked AWS credential in scraped citation URLs.

Adds: classifier engine selection on `process` (transformer default, matches legacy behavior; llm
  opt-in), `climafactskg validate` command (also run automatically at the end of `build`) to catch
  broken RDF output early, ClimateSenseKG wired into `build`, a CI workflow running ruff + pytest, a
  pyproject extras split so matcher/transformer/eval dependencies are optional, and a test suite (58
  tests) covering the previously-untested pure logic.

### Continuous Integration

- Append knowledge graph stats to GitHub release notes
  ([`294bbf6`](https://github.com/climatesense-project/climafacts-kg/commit/294bbf6ee2d2ed38b567bea2bf6e9f97ccf6ff04))

Reads the released data/climafacts_kg.ttl and appends a stats table (triples, ClaimReviews,
  ScholarlyArticles, citations) to the release body semantic-release already generated, rather than
  replacing it.

### Features

- **classifiers**: Split CARDS classifier into a package, add ClimateSenseKG collector
  ([`5306aa9`](https://github.com/climatesense-project/climafacts-kg/commit/5306aa982f77d716fd1fce0ccf48afe740b6dfc7))

Splits the monolithic classifiers/cards.py into a cards/ package (matcher, transformer, taxonomy,
  evaluators, llm/) and adds a ClimateSenseKG SPARQL collector alongside the existing CimpleKG one.


## v1.5.1 (2026-04-07)

### Bug Fixes

- Normalize text literals to avoid multiline Turtle strings
  ([`9299d51`](https://github.com/climatesense-project/climafacts-kg/commit/9299d51057a60db20a8a8dcf6a450b50df7cac85))

Adds _normalize_text() in the builder to collapse newlines in string literals, producing single-line
  Turtle literals compatible with all strict Turtle parsers. Regenerates climafacts_kg.ttl
  accordingly.


## v1.5.0 (2026-03-11)

### Features

- **kg**: Add SKS references builder for RDF graph generation
  ([`7d5e5d4`](https://github.com/climatesense-project/climafacts-kg/commit/7d5e5d4f8aa5331a3eaf842f88efe563a8281074))

Add a new builder in sksreferenceskg.py to map SkepticalScience references to RDF graphs using
  Schema.org, BIBO, and CiTO vocabularies.

- Implement author parsing, DOI normalisation, and page range splitting - Add functions to generate
  references and citations graphs linking articles to their respective references - Integrate
  logging for tracking reference and citation link processing


## v1.4.0 (2025-11-01)

### Features

- Knowledge graph update
  ([`e41297a`](https://github.com/climatesense-project/climafacts-kg/commit/e41297a53e0afb8c64c59f677b55cb236c575f1f))


## v1.3.0 (2025-09-29)

### Bug Fixes

- Merge changes
  ([`4841993`](https://github.com/climatesense-project/climafacts-kg/commit/48419936bf71f467fe4e723474989849aa24c135))


## v1.2.0 (2025-08-26)

### Features

- Migrate from TinyDB to Preserve (Sqlite backend)
  ([`d82f146`](https://github.com/climatesense-project/climafacts-kg/commit/d82f1462f67811f4d157e2e0337b3b7fb8ac6544))

- Added code for collecting misinformers and quotes - Updated dependencies in pyproject.toml -
  Removed tinydb and tinydb-serialization from dependencies - Added preserve package with version
  ^1.2.1 - Added jupyter package to dev dependencies

- Update namespace path to climatesense namespace and add repository metadata
  ([`5b50435`](https://github.com/climatesense-project/climafacts-kg/commit/5b504352537ed8d14e19c9a92b0c52af7740d3ef))


## v1.1.0 (2025-07-31)

### Documentation

- Fix typo in README.md
  ([`bdae25b`](https://github.com/climatesense-project/climafacts-kg/commit/bdae25b225b4b929c493a542f6e7db7f87f42c8e))

- Update README.md
  ([`4507914`](https://github.com/climatesense-project/climafacts-kg/commit/45079147ebc8fd2ead9ef341762f4fccba7503bf))

### Features

- Add new CARDS classifier based on Jaccard similarity, fix namespace and generated RDF
  ([`ac0a1d2`](https://github.com/climatesense-project/climafacts-kg/commit/ac0a1d2b0c4336c59db4cea5e458d2bcd8dc9ccf))


## v1.0.10 (2025-07-29)

### Bug Fixes

- Reformat workflow
  ([`943f7c3`](https://github.com/climatesense-project/climafacts-kg/commit/943f7c3351fddf8ae650b9dc55c996dab5cbf443))

### Documentation

- Add badge to README.md
  ([`ab896fc`](https://github.com/climatesense-project/climafacts-kg/commit/ab896fc9ede3f4d907e6ef988522888a2ba957b1))


## v1.0.9 (2025-07-29)

### Bug Fixes

- Add env token to workflow
  ([`74ddcff`](https://github.com/climatesense-project/climafacts-kg/commit/74ddcffd2734e1be7fa3179968ae2fe17f7330aa))


## v1.0.8 (2025-07-29)

### Bug Fixes

- Workflow trigger
  ([`ffe0129`](https://github.com/climatesense-project/climafacts-kg/commit/ffe0129147a0e3c784faba377773653c824db089))


## v1.0.7 (2025-07-29)

### Bug Fixes

- Use trigger event for publishing graph
  ([`3cc88ef`](https://github.com/climatesense-project/climafacts-kg/commit/3cc88effc9d23a7660b34b66befc800f89bd4bbe))


## v1.0.6 (2025-07-29)

### Bug Fixes

- File extension in semantic-release.yml
  ([`034992c`](https://github.com/climatesense-project/climafacts-kg/commit/034992c8896ca9a95365ef25ff5ae4e48e8651d5))


## v1.0.5 (2025-07-29)

### Bug Fixes

- Vars in semantic-release.yml
  ([`852466c`](https://github.com/climatesense-project/climafacts-kg/commit/852466cc55c58088518958560ff1ec992f9b411a))


## v1.0.4 (2025-07-29)

### Bug Fixes

- Workflows formatting
  ([`d437208`](https://github.com/climatesense-project/climafacts-kg/commit/d4372089d7370be3811a5e7e5a1f67bafda786fb))


## v1.0.3 (2025-07-29)


## v1.0.2 (2025-07-29)

### Bug Fixes

- Missing comma in semantic-release.yml
  ([`6be5143`](https://github.com/climatesense-project/climafacts-kg/commit/6be514396ba4bbef3441eb61d0bf46907debec35))

- Update TTL conversion in semantic-release.yml
  ([`2f30a7a`](https://github.com/climatesense-project/climafacts-kg/commit/2f30a7a54e41bf9d9432d8c45a152eddb81e0d94))


## v1.0.1 (2025-07-29)


## v1.0.0 (2025-07-29)

### Bug Fixes

- Add .nojekyll to gh-pages-publish.yml
  ([`c549db1`](https://github.com/climatesense-project/climafacts-kg/commit/c549db11a505ea7dc7e93790e458b7eb3a6b9749))

- Change quotes in gh-pages-publish.yml
  ([`19c2456`](https://github.com/climatesense-project/climafacts-kg/commit/19c245644f55790fbed310f5d397406438825a9c))

- Remove token from gh-pages-publish.yml
  ([`25ad03b`](https://github.com/climatesense-project/climafacts-kg/commit/25ad03bfd5251c37bc5ae6f73453b64a2eaf8c44))

- Update formatting of gh-pages-publish.yml
  ([`5cd60d6`](https://github.com/climatesense-project/climafacts-kg/commit/5cd60d6f4328e1cbe4fd93bc803d71643f7b093f))

- Update gh-pages-publish.yml token
  ([`eb64ec6`](https://github.com/climatesense-project/climafacts-kg/commit/eb64ec618a528b37f27c9852ae040ec0e99b4844))

Update token access in gh-pages-publish.yml

- Update semantic-release.yml workflow for not publishing on PyPi
  ([`d68b3d6`](https://github.com/climatesense-project/climafacts-kg/commit/d68b3d6e2e7ab33bdf0e600d4f66cb558908ae83))

- Use RDF instead of TTL in gh-pages-publish.yml
  ([`aa2de5e`](https://github.com/climatesense-project/climafacts-kg/commit/aa2de5e4e08a8724c33e9b911162ffd0b3937767))

### Documentation

- Add SkS mappings to README.md 🗺️
  ([`f3410f8`](https://github.com/climatesense-project/climafacts-kg/commit/f3410f832f8dc193baa92d18711b380da88a8151))

- Create README.md
  ([`2f86c20`](https://github.com/climatesense-project/climafacts-kg/commit/2f86c20ae3e4b305692f3cec7ed49e635cb96a02))

- Prettify README.md 💅🏼
  ([`55f11f3`](https://github.com/climatesense-project/climafacts-kg/commit/55f11f3c0838f79b268ab93b7ec64cb8b19182d0))

### Features

- Add TTL publish action
  ([`28cc8aa`](https://github.com/climatesense-project/climafacts-kg/commit/28cc8aabe9ce6576712c7f8dcbd0ff5e86f046a4))

Create gh-pages-publish.yml GitHub action for uploading the TTL ClimaFactsKG to GH-Pages.

- First version of the ClimaFactsKG source code
  ([`c5ff907`](https://github.com/climatesense-project/climafacts-kg/commit/c5ff90798e7d5f84f48fe56cdd99280972ef4529))


## v0.1.0 (2025-07-26)
