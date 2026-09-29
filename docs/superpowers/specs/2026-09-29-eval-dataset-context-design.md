# Review context for the CARDS evaluation datasets

Status: design, awaiting review. Date: 2026-09-29.

## Goal

Give the CARDS evaluation datasets the fact-check **review text** as optional `context` where a review exists,
and make the eval report classifier accuracy **both without and with** that context, so we can see whether context
helps.

Ratings/verdicts are deliberately **not** context: they say nothing about which CARDS narrative a claim promotes and
could leak an "is misinformation" hint into the metrics.

## Findings that constrain the design

- The classifiers already accept `context` (`CARDSClassifierBase.classify(text, context=None)`, and the LLM engine has
  context-aware prompts), and `CARDSInput` already has a `context` field. Nothing populates it.
- `_load_climatesense_dataset` (`classifiers/cards/datasets.py`) already reads an optional `context` column from the
  consensus CSV (line ~466), but `_download_annotations_df` never produces one, so context is always `None`.
- The Google Sheets do **not** carry the review. The `annotations` worksheet has only
  `document_id, source, type, content, is_climate_related, cards_level1/2/3, comments`; `DD1`/`DD2` are dropdown lists
  and `coding` is the annotation form. Annotators labelled from the claim text alone, so **the gold labels are
  claim-only**.
- Where review text is available:
  - **v2** (277 docs, source `CimpleKG (ClaimMap)`): `document_id` is the review URL and joins on `id` to the local
    input file `data/cards_annotations_v2/cards_annotation_v2_full.csv` (`id, data_source, claim_type, claim,
    review`) for all 277. Median review length is about 4,400 characters.
  - **v1** (398 docs): 167 CimpleKG claims with `document_id` `http://data.cimple.eu/claim-review/<hash>`; a single
    SPARQL `VALUES` query on `https://data.cimple.eu/sparql` returned `schema:text` for 150 of 167 (median about 3,500
    characters). The other 231 docs are quotes (DeSmog 167, ClimaFactsKG 64) with no review, so they keep
    `context = None`.
  - **NSLP/ClimateCheck** has a paper `abstract` per claim (evidence, not a review). Out of scope here.
- Reviews are long (p90 7-9k characters, max 86k+), so truncation must be configurable.
- The transformer engine slices `text + context` to 256 characters (`transformer.py`), so it effectively ignores a
  long review. Context evaluation is meaningful for the LLM engine (and the matcher only trivially).

## Design (approach B: sidecar context file)

Consensus CSVs stay untouched. A separate, refreshable sidecar holds the context.

### 1. `climafactskg/classifiers/cards/context.py` (new)

- `load_input_reviews(csv_path) -> dict[str, str]`: `id -> review` from an annotation input CSV.
- `fetch_cimplekg_reviews(uris, *, endpoint=CIMPLEKG_SPARQL_ENDPOINT, chunk_size=100) -> dict[str, str]`: `VALUES`
  query, chunked, `schema:text` per ClaimReview URI. Raises on endpoint failure; URIs with no text are simply absent.
- `build_context_sidecar(document_ids, *, input_csvs=(), fetch_fn=fetch_cimplekg_reviews) -> pd.DataFrame`: columns
  `document_id, context_source ("input_csv" | "cimplekg"), context`. Local inputs win; only ids starting with
  `http://data.cimple.eu/claim-review/` and not found locally are fetched. Logs coverage (`N of M docs have context`).
  `fetch_fn` is injectable so the builder is testable offline.
- `truncate_context(text, max_chars) -> str`: collapse whitespace, cut at the last whitespace at or before
  `max_chars`. `max_chars=None` means no truncation.

### 2. `datasets.py`

- `_load_climatesense_dataset` gains `context_path: str | None` and `max_context_chars: int | None = 1500`.
- If `context_path` exists, read it and left-join onto the consensus `df` by `document_id` as a `context` column, then
  truncate. The existing `row["context"]` hook builds `CARDSInput(text, context)`. A missing sidecar is not an error:
  log a warning, leave context `None` (the fast path stays offline).
- `climatesense_dataset_v1/v2` default `context_path` to `cards_annotations_context.csv` beside their consensus CSV.
- New `build_climatesense_context(version, *, force=False)` builds and writes the sidecar for a dataset (reads the
  cached consensus CSV for the ids; v2 also uses the local input CSV, v1 uses CimpleKG only).
- `nslp_dataset` unchanged.

### 3. `eval.py`

- `evaluate(classifier, dataset, use_context: bool = True)`: when `False`, ignore every case's context (also for the
  duck-typed sequential path). Default keeps today's behavior (context used if present and supported).
- `benchmark_configs(..., context_modes=("none", "with"))`: each config runs once per mode that makes sense (`"with"`
  is skipped for datasets with no context), and the result table gains a `context` column. `print_benchmark` shows it.
- Every context benchmark output carries a note: "gold labels were annotated from claim text only".

### 4. Data, docs, non-goals

- Sidecar files live under `data/` next to the consensus CSVs (untracked, like them); the build step is idempotent and
  cheap to rerun.
- `CLAUDE.md` eval section is updated to describe the sidecar and the with/without-context runs.
- Not in scope: production collectors, changing transformer truncation, re-annotating with context, using NSLP
  abstracts, ratings/verdicts as features.

## Error handling

- Endpoint unreachable during sidecar build: fail loudly, write nothing (no partial sidecar).
- Ids with no review text: `context = None`; counted in the coverage log line.
- Sidecar missing at dataset load: warning, dataset loads without context.
- `use_context=False` never reads contexts, so the without-context run is unaffected by sidecar problems.

## Testing

Offline unit tests (no network, no API key):

- `truncate_context`: whitespace collapse, cut at whitespace boundary, `None`, shorter-than-limit input.
- `build_context_sidecar` with an injected `fetch_fn`: local-first precedence, only CimpleKG-style ids fetched, missing
  ids absent, coverage counts, no fetch when nothing is eligible.
- `fetch_cimplekg_reviews` chunking with a stubbed query function.
- Loader join: a temp consensus CSV plus sidecar yields `CARDSInput.context` for matched ids and `None` otherwise;
  missing sidecar warns and loads; truncation applied.
- `evaluate(..., use_context=False)` with a stub classifier records that no context was passed; `use_context=True`
  passes it.
- Existing tests unchanged.

One cheap live smoke (a few cents, `openai/gpt-4o-mini` via OpenRouter, scratch cache): build the v2 sidecar, run
`evaluate` on a small slice both ways, confirm the report and coverage output.

## Open decisions (deferred, not blocking)

- Whether NSLP's paper `abstract` should be offered as context (it is evidence, not a review).
- Whether to raise the transformer's truncation so a context run means something for that engine.
