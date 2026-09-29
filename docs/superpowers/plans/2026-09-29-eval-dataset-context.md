# Review Context for the CARDS Eval Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach the fact-check review text to the ClimateSense eval datasets as optional, deterministically selected `context`, and make the eval report accuracy both without and with that context.

**Architecture:** A new `classifiers/cards/context.py` holds pure, LLM-free helpers (`select_context`) and the sidecar builder (local input CSVs + one SPARQL fetch from CimpleKG). The dataset loaders left-join the sidecar onto the consensus CSV and run `select_context` per case through the `context` hook that already exists. `evaluate` gains `use_context`, and `benchmark_configs` runs each dataset once per context mode.

**Tech Stack:** Python 3.12, pandas, pydantic-evals, pytest, ruff. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-29-eval-dataset-context-design.md`

## Global Constraints

- No LLM anywhere in context preparation: selection and cleaning are deterministic, offline, and free (regex, word overlap, character budget). The only network access is the plain SPARQL fetch of review text.
- Ratings/verdicts are not context; verdict fragments inside review text are stripped.
- Default context budget is `max_context_chars=800`; overlap threshold default is `0.6`; both are parameters.
- A sentence that restated the claim keeps only its remainder, and only if at least 4 words are left; other sentences need at least 3 words.
- Sentence-based selection, never cutting mid-sentence (last resort: cut at a word boundary with a trailing `…`).
- Consensus CSVs are untouched; context lives in a sidecar `cards_annotations_context.csv` next to each consensus CSV.
- Every with-context report is labelled "gold labels were annotated from claim text only".
- Out of scope: production collectors, changing transformer truncation, NSLP abstracts, re-annotation, LLM summarization.
- Style: Google-style docstrings, 120-char lines, `ruff check` and `ruff format` clean, `zip(..., strict=True)` for parallel lists.
- Tests are offline (no network, API key, or model download). Commits use Conventional Commits and carry **no** `Co-Authored-By` trailer.
- Run tools via uv from the repo root: `uv run pytest ...`, `uv run ruff ...`. Unset `VIRTUAL_ENV` first if it points at another environment.

## Review Focus

- Review or claim cell is `NaN`/`None`/non-string (empty CSV cell): context must be `None`, never a crash or the string `"nan"`.
- Claim text contains regex metacharacters (`(test) [claim]? $5 a+b`): claim matching must not raise or mis-match.
- Duplicate `document_id` rows in the sidecar or consensus: one case per document, no row multiplication from the join.
- Review that is entirely boilerplate/verdict (nothing survives selection): case gets `context=None`, not an empty string.
- Sidecar file missing: dataset still loads (context `None`, one warning) and `benchmark_configs` skips the `"with"` mode for it instead of emitting an identical duplicate row.
- Non-CimpleKG or malformed ids (DeSmog quote ids, ids with `<`, `>` or whitespace): never sent to the SPARQL endpoint.

---

## File Structure

- Create `climafactskg/classifiers/cards/context.py`: `select_context`, `load_input_reviews`, `fetch_cimplekg_reviews`, `build_context_sidecar`, `build_climatesense_context`, `DEFAULT_CONTEXT_PATHS`. One responsibility: preparing review context. No import of `datasets.py`/`eval.py` (avoids cycles).
- Modify `climafactskg/classifiers/cards/datasets.py`: `_attach_context` helper, new parameters on `_load_climatesense_dataset` and `climatesense_dataset_v1/v2`.
- Modify `climafactskg/classifiers/cards/eval.py`: `use_context` in `evaluate`, `context_modes` in `benchmark_configs`, `context` column and note in `print_benchmark`.
- Create `tests/test_cards_context.py`, `tests/test_datasets_context.py`, `tests/test_eval_context.py`.
- Modify `CLAUDE.md` (eval section) and the spec (one deviation note).

Spec deviation: `build_climatesense_context` lives in `context.py` (next to the constants it needs), not `datasets.py`, to keep `datasets.py` from growing further and to avoid an import cycle.

---

### Task 1: `select_context` (pure selection function)

**Files:**
- Create: `climafactskg/classifiers/cards/context.py`
- Create: `tests/test_cards_context.py`

**Interfaces:**
- Produces: `select_context(review: str | None, claim: str, max_chars: int | None = 800, overlap: float = 0.6) -> str` — returns `""` when nothing useful survives.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cards_context.py`:

```python
"""Tests for the deterministic review-context helpers (no network, no LLM)."""

import pytest

from climafactskg.classifiers.cards.context import select_context


class TestSelectContext:
    def test_never_cuts_mid_sentence(self):
        review = (
            "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima. "
            "Mike november oscar papa quebec romeo sierra tango uniform victor whiskey. "
            "Xray yankee zulu alpha bravo charlie delta echo foxtrot golf hotel india."
        )
        out = select_context(review, claim="unrelated", max_chars=150)
        assert out == (
            "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima. "
            "Mike november oscar papa quebec romeo sierra tango uniform victor whiskey."
        )

    def test_drops_claim_restatement_label_and_verdict(self):
        review = (
            "WHAT WAS CLAIMED The moon is made of cheese. OUR VERDICT False. "
            "Scientists have sampled lunar rock. It is basalt."
        )
        out = select_context(review, claim="The moon is made of cheese.")
        assert out == "Scientists have sampled lunar rock. It is basalt."

    def test_drops_paraphrased_restatement_but_keeps_new_information(self):
        review = "Volcanoes emit more CO2 than humans do, the post says. Human emissions are about 100 times larger."
        out = select_context(review, claim="Volcanoes emit more CO2 than humans do")
        assert out == "Human emissions are about 100 times larger."

    def test_strips_inline_verdict_but_keeps_surrounding_content(self):
        review = "Fact Check: The image is fabricated. Verdict: Mostly False The memo does not exist on the site."
        out = select_context(review, claim="q")
        assert "erdict" not in out
        assert "fabricated" in out and "memo does not exist" in out

    def test_oversized_first_sentence_is_cut_at_a_word_boundary_with_ellipsis(self):
        sentence = "Word " * 60 + "end."
        out = select_context(sentence, claim="unrelated", max_chars=100)
        assert out.endswith("…")
        assert len(out) <= 101
        body = out[:-1]
        assert sentence.startswith(body)
        assert sentence[len(body)] == " "  # cut landed on a word boundary

    def test_everything_dropped_returns_empty_string(self):
        assert select_context("OUR VERDICT False.", claim="x") == ""

    def test_no_budget_keeps_all_surviving_sentences(self):
        review = "First useful sentence here. Second useful sentence here."
        assert select_context(review, claim="zzz", max_chars=None) == review

    def test_abbreviations_do_not_split_sentences(self):
        review = "The U.S. emitted 5 Gt in 2020. Dr. Smith disagrees with the figure."
        assert select_context(review, claim="unrelated topic here", max_chars=800) == review
        assert select_context(review, claim="unrelated topic here", max_chars=45) == "The U.S. emitted 5 Gt in 2020."

    @pytest.mark.parametrize("review", ["", None, "   "])
    def test_empty_or_missing_review_returns_empty_string(self, review):
        assert select_context(review, claim="x") == ""

    def test_whitespace_is_collapsed(self):
        review = "Alpha   beta\tgamma delta.\n\nEpsilon zeta eta theta."
        assert select_context(review, claim="q") == "Alpha beta gamma delta. Epsilon zeta eta theta."

    def test_claim_with_regex_metacharacters_does_not_raise(self):
        claim = "A (test) [claim]? costs $5 a+b"
        review = f"WHAT WAS CLAIMED {claim} Independent analysts found the figures were wrong."
        assert select_context(review, claim=claim) == "Independent analysts found the figures were wrong."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cards_context.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'climafactskg.classifiers.cards.context'`.

- [ ] **Step 3: Write the implementation**

Create `climafactskg/classifiers/cards/context.py`:

```python
"""Deterministic, LLM-free preparation of fact-check review context for the CARDS eval datasets.

Selecting and cleaning context uses only regexes, word overlap and a character budget, so a with-context eval is
reproducible and free. The one network access (in :func:`fetch_cimplekg_reviews`) is a plain SPARQL fetch of review
text.
"""

import re

_DOT = "․"  # stand-in for "." inside abbreviations so the sentence splitter ignores them
_CLAIM_MARK = "⁃"  # marks where the verbatim claim was removed from a review
_LEAD_PUNCT = ",;:-–—\"'“” \t"

_PROTECT_RES = (
    re.compile(r"\b(?:[A-Za-z]\.){2,}"),  # U.S., e.g., i.e., U.K.
    re.compile(r"\b(?:Dr|Mr|Mrs|Ms|Prof|St|Sr|Jr|vs|Inc|Ltd|Co|No)\."),  # titles / company suffixes
    re.compile(r"\b[A-Z]\.(?=\s+[A-Z])"),  # single initials: "J. Smith"
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[\"'“‘(]*[A-Z0-9])")
_LEADING_LABEL_RE = re.compile(
    r"^\s*(?:WHAT WAS CLAIMED|What was claimed|THE STATEMENT|The Statement|THE CLAIM|The Claim|OUR VERDICT|"
    r"FACT CHECK|Fact Check|Fact check|CLAIM|Claim|Statement)\b\s*[:\-–]?\s*"
)
_VERDICT_RE = re.compile(
    r"\b(?:our\s+)?(?:verdict|rating)\s*[:\-–]?\s*(?:mostly\s+|partly\s+|half\s+)?"
    r"(?:false|true|misleading|correct|incorrect|unproven|unverified|satire|fake|inaccurate|missing context|mixture)"
    r"\b\.?",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9]+")


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _mark_claim(text: str, claim: str) -> str:
    """Replaces every verbatim occurrence of *claim* in *text* with a marker."""
    claim = _collapse(claim)
    if not claim:
        return text
    return re.sub(re.escape(claim), f" {_CLAIM_MARK} ", text, flags=re.IGNORECASE)


def select_context(review: str | None, claim: str, max_chars: int | None = 800, overlap: float = 0.6) -> str:
    """Selects the informative lead of a fact-check review, within a character budget.

    Steps: collapse whitespace; mark and remove the verbatim claim; strip verdict fragments and leading labels;
    split into sentences (abbreviation-safe); drop sentences that restate the claim; add whole sentences until
    the budget is reached. Never cuts mid-sentence, except as a last resort when even the first surviving
    sentence exceeds the budget (then it is cut at a word boundary and ends with an ellipsis).

    Args:
        review: Full review text (may be ``None`` or empty).
        claim: The claim the review is about; used to drop sentences that only restate it.
        max_chars: Character budget for the returned text. ``None`` disables the budget.
        overlap: A sentence with at least four words is dropped when at least this fraction of its words
            appear in *claim*.

    Returns:
        The selected context, or ``""`` when nothing useful survives.
    """
    text = _collapse(review or "")
    if not text:
        return ""
    text = _mark_claim(text, claim)
    text = _collapse(_VERDICT_RE.sub(" ", text))
    for _ in range(3):  # headers can stack: "FACT CHECK: WHAT WAS CLAIMED ..."
        stripped = _LEADING_LABEL_RE.sub("", text)
        if stripped == text:
            break
        text = stripped
    for pattern in _PROTECT_RES:
        text = pattern.sub(lambda m: m.group(0).replace(".", _DOT), text)

    claim_words = set(_WORD_RE.findall(claim.lower()))
    kept: list[str] = []
    for raw in _SENTENCE_SPLIT_RE.split(text):
        sentence = raw.replace(_DOT, ".").strip()
        if _CLAIM_MARK in sentence:  # keep only what is left of a sentence that restated the claim
            sentence = _collapse(sentence.replace(_CLAIM_MARK, " ")).lstrip(_LEAD_PUNCT)
            sentence = _LEADING_LABEL_RE.sub("", sentence).lstrip(_LEAD_PUNCT)
            if len(_WORD_RE.findall(sentence.lower())) < 4:
                continue
        words = _WORD_RE.findall(sentence.lower())
        if len(words) < 3:
            continue
        if len(words) >= 4 and claim_words and sum(w in claim_words for w in words) / len(words) >= overlap:
            continue
        kept.append(sentence)
    if not kept:
        return ""
    if max_chars is None:
        return " ".join(kept)

    chosen: list[str] = []
    used = 0
    for sentence in kept:
        cost = len(sentence) + (1 if chosen else 0)
        if used + cost > max_chars:
            break
        chosen.append(sentence)
        used += cost
    if chosen:
        return " ".join(chosen)
    first = kept[0]
    cut = first[: max_chars + 1].rsplit(" ", 1)[0].rstrip(",;:- ")
    return (cut or first[:max_chars]) + "…"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cards_context.py -v`
Expected: PASS (13 tests).

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg/classifiers/cards/context.py tests/test_cards_context.py
uv run ruff format climafactskg/classifiers/cards/context.py tests/test_cards_context.py
uv run pytest tests -q
git add climafactskg/classifiers/cards/context.py tests/test_cards_context.py
git commit -m "feat(eval): add deterministic sentence-based review context selection"
```

---

### Task 2: Sidecar sources (local inputs + CimpleKG fetch) and builder

**Files:**
- Modify: `climafactskg/classifiers/cards/context.py`
- Modify: `tests/test_cards_context.py`

**Interfaces:**
- Consumes: `select_context` is unrelated here; this task adds independent functions to the same module.
- Produces:
  - `load_input_reviews(csv_path: str) -> dict[str, str]`
  - `fetch_cimplekg_reviews(uris, *, endpoint=CIMPLEKG_SPARQL_ENDPOINT, chunk_size=100, query_fn=query_sparqlendpoint) -> dict[str, str]`
  - `build_context_sidecar(document_ids, *, input_csvs=(), fetch_fn=fetch_cimplekg_reviews) -> pd.DataFrame` with columns `document_id, context_source, context`
  - `build_climatesense_context(version: Literal["v1", "v2"], *, consensus_path=None, context_path=None, input_csvs=None, fetch_fn=fetch_cimplekg_reviews, force=False) -> pd.DataFrame`
  - `DEFAULT_CONTEXT_PATHS: dict[str, str]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cards_context.py` (add the new imports at the top of the file, merging with the existing import line):

```python
import pandas as pd

from climafactskg.classifiers.cards.context import (
    DEFAULT_CONTEXT_PATHS,
    build_climatesense_context,
    build_context_sidecar,
    fetch_cimplekg_reviews,
    load_input_reviews,
    select_context,
)

CIMPLE = "http://data.cimple.eu/claim-review/"


class TestLoadInputReviews:
    def test_maps_id_to_review_and_skips_blank_reviews(self, tmp_path):
        path = tmp_path / "inputs.csv"
        pd.DataFrame(
            {
                "id": ["https://a.example/1", "https://a.example/2", "https://a.example/3"],
                "data_source": ["x", "x", "x"],
                "claim_type": ["claim", "claim", "claim"],
                "claim": ["c1", "c2", "c3"],
                "review": ["Review one.", "", None],
            }
        ).to_csv(path, index=False)

        assert load_input_reviews(str(path)) == {"https://a.example/1": "Review one."}


class TestFetchCimpleKGReviews:
    def test_chunks_dedupes_and_returns_only_found_texts(self):
        calls = []

        def query_fn(endpoint, query):
            calls.append((endpoint, query))
            found = [(u, f"text for {u}") for u in (f"{CIMPLE}a", f"{CIMPLE}c") if f"<{u}>" in query]
            return pd.DataFrame(found, columns=["rev", "text"]) if found else pd.DataFrame()

        uris = [f"{CIMPLE}a", f"{CIMPLE}b", f"{CIMPLE}c", f"{CIMPLE}d", f"{CIMPLE}a"]
        result = fetch_cimplekg_reviews(uris, chunk_size=2, query_fn=query_fn, endpoint="http://endpoint.test")

        assert result == {f"{CIMPLE}a": f"text for {CIMPLE}a", f"{CIMPLE}c": f"text for {CIMPLE}c"}
        assert len(calls) == 2  # 4 unique uris / chunk_size 2
        assert all(endpoint == "http://endpoint.test" for endpoint, _ in calls)
        assert f"<{CIMPLE}a>" in calls[0][1] and f"<{CIMPLE}b>" in calls[0][1]

    def test_ignores_blank_and_non_string_texts(self):
        def query_fn(endpoint, query):
            return pd.DataFrame({"rev": [f"{CIMPLE}a", f"{CIMPLE}b"], "text": ["   ", None]})

        assert fetch_cimplekg_reviews([f"{CIMPLE}a", f"{CIMPLE}b"], query_fn=query_fn) == {}


class TestBuildContextSidecar:
    def test_local_inputs_win_and_only_cimplekg_ids_are_fetched(self, tmp_path):
        inputs = tmp_path / "inputs.csv"
        pd.DataFrame({"id": [f"{CIMPLE}local"], "review": ["Local review."]}).to_csv(inputs, index=False)
        fetched_with = []

        def fetch_fn(uris):
            fetched_with.append(list(uris))
            return {f"{CIMPLE}remote": "Remote review."}

        ids = [f"{CIMPLE}local", f"{CIMPLE}remote", f"{CIMPLE}missing", "https://skepticalscience.com/skeptic_X.htm"]
        df = build_context_sidecar(ids, input_csvs=[str(inputs)], fetch_fn=fetch_fn)

        assert fetched_with == [[f"{CIMPLE}remote", f"{CIMPLE}missing"]]  # local id and non-CimpleKG id not fetched
        assert list(df.columns) == ["document_id", "context_source", "context"]
        by_id = df.set_index("document_id")
        assert by_id.loc[f"{CIMPLE}local", "context_source"] == "input_csv"
        assert by_id.loc[f"{CIMPLE}remote", "context_source"] == "cimplekg"
        assert f"{CIMPLE}missing" not in by_id.index
        assert "https://skepticalscience.com/skeptic_X.htm" not in by_id.index

    def test_malformed_ids_are_never_fetched(self):
        fetched_with = []

        def fetch_fn(uris):
            fetched_with.append(list(uris))
            return {}

        bad = [f"{CIMPLE}has space", f"{CIMPLE}a>b", f"{CIMPLE}x<y", f"{CIMPLE}ok"]
        build_context_sidecar(bad, fetch_fn=fetch_fn)

        assert fetched_with == [[f"{CIMPLE}ok"]]

    def test_no_fetch_when_nothing_is_eligible(self):
        def fetch_fn(uris):
            raise AssertionError("fetch_fn must not be called")

        df = build_context_sidecar(["https://example.org/quote"], fetch_fn=fetch_fn)

        assert df.empty
        assert list(df.columns) == ["document_id", "context_source", "context"]


class TestBuildClimatesenseContext:
    def _consensus(self, tmp_path, ids):
        path = tmp_path / "consensus.csv"
        pd.DataFrame({"document_id": ids, "content": ["c"] * len(ids), "cards_code": ["1_1"] * len(ids)}).to_csv(
            path, index=False
        )
        return str(path)

    def test_writes_sidecar_then_reuses_it_unless_forced(self, tmp_path):
        consensus = self._consensus(tmp_path, [f"{CIMPLE}a"])
        sidecar = str(tmp_path / "context.csv")
        calls = []

        def fetch_fn(uris):
            calls.append(list(uris))
            return {f"{CIMPLE}a": f"Review {len(calls)}."}

        first = build_climatesense_context("v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn)
        again = build_climatesense_context("v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn)
        forced = build_climatesense_context(
            "v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn, force=True
        )

        assert first.loc[0, "context"] == "Review 1."
        assert again.loc[0, "context"] == "Review 1."  # cached file reused, no second fetch
        assert forced.loc[0, "context"] == "Review 2."
        assert len(calls) == 2
        assert pd.read_csv(sidecar).loc[0, "context"] == "Review 2."
        assert not (tmp_path / "context.csv.tmp").exists()

    def test_failed_fetch_leaves_no_sidecar(self, tmp_path):
        consensus = self._consensus(tmp_path, [f"{CIMPLE}a"])
        sidecar = tmp_path / "context.csv"

        def fetch_fn(uris):
            raise RuntimeError("endpoint down")

        with pytest.raises(RuntimeError, match="endpoint down"):
            build_climatesense_context("v1", consensus_path=consensus, context_path=str(sidecar), fetch_fn=fetch_fn)

        assert not sidecar.exists()

    def test_missing_consensus_csv_raises_a_helpful_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="consensus"):
            build_climatesense_context(
                "v1", consensus_path=str(tmp_path / "nope.csv"), context_path=str(tmp_path / "c.csv")
            )

    def test_default_paths_sit_next_to_the_consensus_csvs(self):
        assert DEFAULT_CONTEXT_PATHS["v1"] == "data/cards_annotations_v2/cards_annotations_context.csv"
        assert DEFAULT_CONTEXT_PATHS["v2"] == "data/cards_annotations_v2b/cards_annotations_context.csv"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cards_context.py -v`
Expected: FAIL/ERROR — `ImportError: cannot import name 'DEFAULT_CONTEXT_PATHS'` (and the other new names).

- [ ] **Step 3: Write the implementation**

In `climafactskg/classifiers/cards/context.py`, replace the import block at the top (`import re`) with:

```python
import logging
import os
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Literal

import pandas as pd

from climafactskg.utils import query_sparqlendpoint

logger = logging.getLogger(__name__)

# Same endpoint as collectors/cimplekg.py; duplicated (not imported) so classifiers stay independent of collectors.
CIMPLEKG_SPARQL_ENDPOINT = "https://data.cimple.eu/sparql"
CIMPLEKG_REVIEW_PREFIX = "http://data.cimple.eu/claim-review/"
_SAFE_URI_RE = re.compile(r"^[A-Za-z0-9:/._~%-]+$")

_DATASET_FILES: dict[str, dict] = {
    # v1's cached consensus lives in the "cards_annotations_v2" directory and v2's in "cards_annotations_v2b" (naming
    # quirk kept from the dataset factories). Only round 2 has local annotation input files with review text.
    "v1": {
        "consensus": "data/cards_annotations_v2/cards_annotations_consensus.csv",
        "context": "data/cards_annotations_v2/cards_annotations_context.csv",
        "inputs": (),
    },
    "v2": {
        "consensus": "data/cards_annotations_v2b/cards_annotations_consensus.csv",
        "context": "data/cards_annotations_v2b/cards_annotations_context.csv",
        "inputs": ("data/cards_annotations_v2/cards_annotation_v2_full.csv",),
    },
}
DEFAULT_CONTEXT_PATHS: dict[str, str] = {version: files["context"] for version, files in _DATASET_FILES.items()}
```

Then append to the end of the same file:

```python
def _is_cimplekg_review_uri(document_id: str) -> bool:
    return document_id.startswith(CIMPLEKG_REVIEW_PREFIX) and bool(_SAFE_URI_RE.match(document_id))


def load_input_reviews(csv_path: str) -> dict[str, str]:
    """Loads ``id -> review`` from an annotation input CSV (columns ``id`` and ``review``); blank reviews are skipped."""
    df = pd.read_csv(csv_path, usecols=["id", "review"], encoding="utf-8-sig").dropna()
    return {
        str(doc_id): str(review)
        for doc_id, review in zip(df["id"], df["review"], strict=True)
        if str(review).strip()
    }


def fetch_cimplekg_reviews(
    uris: Iterable[str],
    *,
    endpoint: str = CIMPLEKG_SPARQL_ENDPOINT,
    chunk_size: int = 100,
    query_fn: Callable = query_sparqlendpoint,
) -> dict[str, str]:
    """Fetches ``schema:text`` (the review text) for CimpleKG ClaimReview URIs, chunked into ``VALUES`` queries.

    Args:
        uris: ClaimReview URIs. Duplicates are collapsed.
        endpoint: SPARQL endpoint URL.
        chunk_size: URIs per query.
        query_fn: ``(endpoint, query) -> DataFrame`` with columns ``rev`` and ``text``; injectable for tests.

    Returns:
        ``uri -> review text``. URIs without a non-blank ``schema:text`` are absent. Endpoint errors propagate.
    """
    unique = list(dict.fromkeys(uris))
    reviews: dict[str, str] = {}
    for start in range(0, len(unique), chunk_size):
        values = " ".join(f"<{uri}>" for uri in unique[start : start + chunk_size])
        query = (
            "PREFIX schema: <http://schema.org/> "
            f"SELECT ?rev ?text WHERE {{ VALUES ?rev {{ {values} }} ?rev schema:text ?text }}"
        )
        df = query_fn(endpoint, query)
        if df is None or df.empty:
            continue
        for rev, text in zip(df["rev"], df["text"], strict=True):
            if isinstance(text, str) and text.strip():
                reviews.setdefault(str(rev), text)
    return reviews


def build_context_sidecar(
    document_ids: Iterable[str],
    *,
    input_csvs: Sequence[str] = (),
    fetch_fn: Callable[[list[str]], dict[str, str]] = fetch_cimplekg_reviews,
) -> pd.DataFrame:
    """Builds the review-context sidecar for annotated documents.

    Local annotation input CSVs win; documents not found there whose id is a well-formed CimpleKG ClaimReview URI
    are fetched with *fetch_fn*. Everything else (e.g. quotes with no review) is simply absent.

    Returns:
        DataFrame with columns ``document_id``, ``context_source`` (``"input_csv"`` or ``"cimplekg"``), ``context``.
    """
    ids = list(dict.fromkeys(str(doc_id) for doc_id in document_ids))
    local: dict[str, str] = {}
    for path in input_csvs:
        for doc_id, review in load_input_reviews(path).items():
            local.setdefault(doc_id, review)
    rows = [{"document_id": i, "context_source": "input_csv", "context": local[i]} for i in ids if i in local]

    to_fetch = [i for i in ids if i not in local and _is_cimplekg_review_uri(i)]
    fetched = fetch_fn(to_fetch) if to_fetch else {}
    rows += [{"document_id": i, "context_source": "cimplekg", "context": fetched[i]} for i in to_fetch if i in fetched]

    logger.info(
        "Review context found for %d of %d documents (%d local, %d from CimpleKG)",
        len(rows),
        len(ids),
        len(rows) - len([r for r in rows if r["context_source"] == "cimplekg"]),
        len([r for r in rows if r["context_source"] == "cimplekg"]),
    )
    return pd.DataFrame(rows, columns=["document_id", "context_source", "context"])


def build_climatesense_context(
    version: Literal["v1", "v2"],
    *,
    consensus_path: str | None = None,
    context_path: str | None = None,
    input_csvs: Sequence[str] | None = None,
    fetch_fn: Callable[[list[str]], dict[str, str]] = fetch_cimplekg_reviews,
    force: bool = False,
) -> pd.DataFrame:
    """Builds (or loads) the review-context sidecar for a ClimateSense annotation round.

    Reads the ids from the cached consensus CSV, so run the dataset factory once first to create it. An existing
    sidecar is returned as-is unless *force* is set. The sidecar is written atomically, so a failed fetch leaves no
    partial file.

    Args:
        version: ``"v1"`` or ``"v2"``.
        consensus_path: Override the consensus CSV path (defaults to the dataset's cache path).
        context_path: Override the sidecar path (defaults to :data:`DEFAULT_CONTEXT_PATHS`).
        input_csvs: Override the local annotation input CSVs (defaults per version).
        fetch_fn: Review fetcher; injectable for tests.
        force: Rebuild even if the sidecar exists.

    Returns:
        The sidecar DataFrame (``document_id``, ``context_source``, ``context``).
    """
    files = _DATASET_FILES[version]
    consensus_path = consensus_path or files["consensus"]
    context_path = context_path or files["context"]
    inputs = files["inputs"] if input_csvs is None else input_csvs

    if os.path.exists(context_path) and not force:
        return pd.read_csv(context_path)
    if not os.path.exists(consensus_path):
        raise FileNotFoundError(
            f"The consensus CSV was not found at {consensus_path}; build the dataset once "
            f"(e.g. climatesense_dataset_{version}()) to create it before building its context."
        )

    ids = pd.read_csv(consensus_path)["document_id"]
    sidecar = build_context_sidecar(ids, input_csvs=inputs, fetch_fn=fetch_fn)
    os.makedirs(os.path.dirname(context_path) or ".", exist_ok=True)
    tmp_path = f"{context_path}.tmp"
    sidecar.to_csv(tmp_path, index=False)
    os.replace(tmp_path, context_path)
    return sidecar
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cards_context.py -v`
Expected: PASS (all tests, including Task 1's).

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg/classifiers/cards/context.py tests/test_cards_context.py
uv run ruff format climafactskg/classifiers/cards/context.py tests/test_cards_context.py
uv run pytest tests -q
git add climafactskg/classifiers/cards/context.py tests/test_cards_context.py
git commit -m "feat(eval): build a review-context sidecar from local inputs and CimpleKG"
```

---

### Task 3: Dataset loader integration

**Files:**
- Modify: `climafactskg/classifiers/cards/datasets.py` (imports near line 37-57; `_load_climatesense_dataset` at ~404; `climatesense_dataset_v1` at ~483; `climatesense_dataset_v2` at ~531)
- Create: `tests/test_datasets_context.py`

**Interfaces:**
- Consumes: `select_context`, `DEFAULT_CONTEXT_PATHS` from `context.py`.
- Produces: `climatesense_dataset_v1/v2(..., context_path: str | None = DEFAULT_CONTEXT_PATHS[...], max_context_chars: int | None = 800)`; `_load_climatesense_dataset(..., context_path, max_context_chars)`; cases carry `CARDSInput(text, context)` where context is the selected review text or `None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_datasets_context.py`:

```python
"""Tests that the ClimateSense dataset loaders attach and select review context from the sidecar."""

import logging

import pandas as pd

from climafactskg.classifiers.cards.datasets import climatesense_dataset_v1

CIMPLE = "http://data.cimple.eu/claim-review/"


def _write_consensus(tmp_path, rows):
    path = tmp_path / "consensus.csv"
    pd.DataFrame(
        [
            {
                "document_id": doc_id,
                "content": content,
                "source": "CimpleKG",
                "type": "claim",
                "cards_code": "1_1",
                "agreement_info": "{}",
            }
            for doc_id, content in rows
        ]
    ).to_csv(path, index=False)
    return str(path)


def _write_sidecar(tmp_path, rows):
    path = tmp_path / "context.csv"
    pd.DataFrame(rows, columns=["document_id", "context_source", "context"]).to_csv(path, index=False)
    return str(path)


def _contexts(dataset):
    return {case.name: case.inputs.context for case in dataset.cases}


class TestLoaderContext:
    def test_attaches_selected_context_and_leaves_others_none(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "The moon is cheese."), (f"{CIMPLE}b", "Other claim.")])
        sidecar = _write_sidecar(
            tmp_path,
            [
                (
                    f"{CIMPLE}a",
                    "cimplekg",
                    "WHAT WAS CLAIMED The moon is cheese. OUR VERDICT False. Scientists sampled the lunar rock and found basalt.",
                )
            ],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds) == {
            f"{CIMPLE}a": "Scientists sampled the lunar rock and found basalt.",
            f"{CIMPLE}b": None,
        }

    def test_missing_sidecar_still_loads_with_a_warning(self, tmp_path, caplog):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])

        with caplog.at_level(logging.WARNING):
            ds = climatesense_dataset_v1(path=consensus, context_path=str(tmp_path / "absent.csv"))

        assert _contexts(ds) == {f"{CIMPLE}a": None}
        assert any("context" in record.message.lower() for record in caplog.records)

    def test_context_path_none_disables_context_without_warning(self, tmp_path, caplog):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])

        with caplog.at_level(logging.WARNING):
            ds = climatesense_dataset_v1(path=consensus, context_path=None)

        assert _contexts(ds) == {f"{CIMPLE}a": None}
        assert not caplog.records

    def test_duplicate_sidecar_rows_do_not_duplicate_cases(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        sidecar = _write_sidecar(
            tmp_path,
            [
                (f"{CIMPLE}a", "input_csv", "First independent finding here."),
                (f"{CIMPLE}a", "cimplekg", "Second independent finding here."),
            ],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert len(ds.cases) == 1
        assert _contexts(ds)[f"{CIMPLE}a"] == "First independent finding here."

    def test_blank_and_boilerplate_only_reviews_become_none(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a."), (f"{CIMPLE}b", "Claim b.")])
        sidecar = _write_sidecar(
            tmp_path,
            [(f"{CIMPLE}a", "cimplekg", ""), (f"{CIMPLE}b", "cimplekg", "OUR VERDICT False.")],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds) == {f"{CIMPLE}a": None, f"{CIMPLE}b": None}

    def test_max_context_chars_is_applied(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        review = " ".join(f"Sentence number {i} says something entirely new and different." for i in range(30))
        sidecar = _write_sidecar(tmp_path, [(f"{CIMPLE}a", "cimplekg", review)])

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar, max_context_chars=200)

        context = _contexts(ds)[f"{CIMPLE}a"]
        assert 0 < len(context) <= 200
        assert context.endswith(".")  # whole sentences only

    def test_claim_with_regex_metacharacters_loads(self, tmp_path):
        claim = "A (test) [claim]? costs $5 a+b"
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", claim)])
        sidecar = _write_sidecar(
            tmp_path, [(f"{CIMPLE}a", "cimplekg", f"{claim} Independent analysts found the figures were wrong.")]
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds)[f"{CIMPLE}a"] == "Independent analysts found the figures were wrong."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_datasets_context.py -v`
Expected: FAIL — `TypeError: climatesense_dataset_v1() got an unexpected keyword argument 'context_path'`.

- [ ] **Step 3: Write the implementation**

In `climafactskg/classifiers/cards/datasets.py`:

1. Add to the imports (after `from pydantic_evals import Case, Dataset`, keeping isort order relative to the existing `from .evaluators import (...)` block):

```python
from .context import DEFAULT_CONTEXT_PATHS, select_context
```

2. Add this helper immediately above `def _load_climatesense_dataset(`:

```python
def _attach_context(df: pd.DataFrame, context_path: str | None, max_context_chars: int | None) -> pd.DataFrame:
    """Left-joins the review-context sidecar onto *df* as a ``context`` column, selecting text per case.

    A missing sidecar is not an error: it logs a warning and leaves every context ``None``. ``context_path=None``
    disables context silently. Documents without a usable review get ``None``.
    """
    df = df.drop(columns=["context"], errors="ignore")
    if context_path is None:
        return df.assign(context=None)
    if not os.path.exists(context_path):
        logger.warning("Review-context sidecar not found at %s; loading without context", context_path)
        return df.assign(context=None)

    sidecar = (
        pd.read_csv(context_path)[["document_id", "context"]]
        .dropna(subset=["context"])
        .drop_duplicates(subset=["document_id"])
    )
    df = df.merge(sidecar, on="document_id", how="left")
    df["context"] = [
        (select_context(review, str(claim), max_chars=max_context_chars) or None) if isinstance(review, str) else None
        for review, claim in zip(df["context"], df["content"], strict=True)
    ]
    logger.info("Review context attached to %d of %d cases", int(df["context"].notna().sum()), len(df))
    return df
```

3. In `_load_climatesense_dataset`: add the two parameters to the signature after `dataset_name: str,`:

```python
    context_path: str | None = None,
    max_context_chars: int | None = 800,
```

Add to its docstring `Args:` list:

```
        context_path: Path to the review-context sidecar CSV (see :mod:`.context`), or ``None`` for no context.
        max_context_chars: Character budget per case for the selected review context (``None`` = unlimited).
```

Then, right after the line `df = df.drop_duplicates(subset=["document_id"]).reset_index(drop=True)` / the `if limit is not None: df = df.head(limit)` block (i.e. after the limit is applied, before `limit_note`), insert:

```python
    df = _attach_context(df, context_path, max_context_chars)
```

The existing hook `context = row["context"] if "context" in df.columns and pd.notna(row.get("context")) else None` now receives the selected text; leave it unchanged.

4. In `climatesense_dataset_v1` add parameters after `min_annotators: int = 3,`:

```python
    context_path: str | None = DEFAULT_CONTEXT_PATHS["v1"],
    max_context_chars: int | None = 800,
```

pass them through in the `_load_climatesense_dataset(...)` call (`context_path=context_path, max_context_chars=max_context_chars,`), and add to its docstring `Args:`:

```
        context_path: Review-context sidecar CSV (built by ``build_climatesense_context("v1")``); a missing file only
            logs a warning. ``None`` disables context.
        max_context_chars: Character budget per case for the selected review context.
```

5. Do the same in `climatesense_dataset_v2` with `DEFAULT_CONTEXT_PATHS["v2"]` (its `min_annotators` default is `2`; add the two new parameters after it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_datasets_context.py tests/test_cards_context.py -v`
Expected: PASS. Then `uv run pytest tests -q` — all existing tests still pass.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg tests
uv run ruff format climafactskg tests
git add climafactskg/classifiers/cards/datasets.py tests/test_datasets_context.py
git commit -m "feat(eval): attach selected review context to the ClimateSense datasets"
```

---

### Task 4: Evaluate with and without context

**Files:**
- Modify: `climafactskg/classifiers/cards/eval.py` (`evaluate` ~96-169, `benchmark_configs` ~172-338, `print_benchmark` ~341-390)
- Create: `tests/test_eval_context.py`

**Interfaces:**
- Consumes: `CARDSInput(text, context)` cases from Task 3.
- Produces:
  - `evaluate(classifier, dataset, use_context: bool = True)`
  - `benchmark_configs(configs, datasets, context_modes: Sequence[Literal["none", "with"]] = ("none", "with"))` → rows gain a `context` column (`"none"`/`"with"`); the `"with"` mode is skipped for datasets that have no context.
  - `print_benchmark` shows a `Ctx` column and, when any row has `context == "with"`, the note "gold labels were annotated from claim text only".

- [ ] **Step 1: Write the failing tests**

Create `tests/test_eval_context.py`:

```python
"""Tests for evaluating with and without review context (stub classifier, no models, no network)."""

import pandas as pd
from pydantic_evals import Case, Dataset

from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import CARDSInput, benchmark_configs, evaluate, print_benchmark
from climafactskg.classifiers.cards.evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch


class _Recorder(CARDSClassifierBase):
    """Always answers 1_1 and records the context each item was classified with."""

    def __init__(self):
        self.seen: list[str | None] = []

    def classify(self, text, context=None):
        self.seen.append(context)
        return "1_1"


def _dataset(name, contexts):
    cases = [
        Case(name=f"case{i}", inputs=CARDSInput(text=f"claim {i}", context=ctx), expected_output=["1_1"])
        for i, ctx in enumerate(contexts)
    ]
    return Dataset(cases=cases, name=name, evaluators=[CARDSOneOfMatch(), CARDSHierarchicalMatch()])


class TestEvaluateUseContext:
    def test_use_context_true_passes_contexts(self):
        clf = _Recorder()
        evaluate(clf, _dataset("d", ["ctx a", None, "ctx c"]), use_context=True)
        assert clf.seen == ["ctx a", None, "ctx c"]

    def test_use_context_false_passes_none_even_when_present(self):
        clf = _Recorder()
        report = evaluate(clf, _dataset("d", ["ctx a", "ctx b"]), use_context=False)
        assert clf.seen == [None, None]
        assert len(report.cases) == 2  # scoring still finds every case's prediction

    def test_default_keeps_using_context(self):
        clf = _Recorder()
        evaluate(clf, _dataset("d", ["ctx a"]))
        assert clf.seen == ["ctx a"]


class TestBenchmarkContextModes:
    def test_runs_both_modes_when_a_dataset_has_context(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"with_ctx": _dataset("d", ["ctx a", "ctx b"])})

        assert list(df["context"]) == ["none", "with"]
        assert list(df["n_cases"]) == [2, 2]
        assert clf.seen == [None, None, "ctx a", "ctx b"]

    def test_skips_with_mode_for_datasets_without_context(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"plain": _dataset("d", [None, None])})

        assert list(df["context"]) == ["none"]

    def test_context_modes_can_be_restricted(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"d": _dataset("d", ["ctx"])}, context_modes=("with",))

        assert list(df["context"]) == ["with"]
        assert clf.seen == ["ctx"]


class TestPrintBenchmark:
    def test_prints_claim_only_note_when_a_with_context_row_exists(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "with", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" in " ".join(capsys.readouterr().out.split())

    def test_no_note_without_with_context_rows(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "none", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" not in " ".join(capsys.readouterr().out.split())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_eval_context.py -v`
Expected: FAIL — `TypeError: evaluate() got an unexpected keyword argument 'use_context'`.

- [ ] **Step 3: Write the implementation**

In `climafactskg/classifiers/cards/eval.py`:

1. Add `from collections.abc import Sequence` to the imports, between `import logging` and the existing `from typing import Any, Literal, cast` (isort order).

2. `evaluate`: change the signature and docstring, and the prediction contexts. Replace `def evaluate(classifier, dataset: Dataset):` with:

```python
def evaluate(classifier, dataset: Dataset, use_context: bool = True):
```

Add to its docstring `Args:`:

```
        use_context: When ``False``, ignore every case's ``context`` and classify the claim text alone (the gold
            labels are claim-only annotations, so this is the like-for-like run). Defaults to ``True``: contexts
            are used when present and the classifier supports them.
```

Right after the existing `contexts = [inp.context if isinstance(inp, CARDSInput) else None for inp in inputs]` line in `evaluate`, add:

```python
    # `contexts` (the dataset's own) keys the prediction lookup below; `predict_contexts` is what the classifier sees.
    predict_contexts = contexts if use_context else [None] * len(texts)
    if use_context and any(contexts):
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")
```

Then in `evaluate` replace the three uses of `contexts` in the prediction block (the `if any(contexts) and supports_context:` test, `classifier.classify_batch(texts, contexts=contexts)`, and the sequential `use_context = any(contexts) and supports_context` / `zip(texts, contexts, ...)`) with `predict_contexts`. Note the local variable named `use_context` in the sequential branch now shadows the new parameter; rename that local to `pass_context`:

```python
        pass_context = any(predict_contexts) and supports_context
        preds = [
            classifier.classify(t, context=ctx) if pass_context else classifier.classify(t)
            for t, ctx in track(zip(texts, predict_contexts, strict=True), description="Classifying...", total=len(texts))
        ]
```

Leave the `cache = {(t, c): p for t, c, p in zip(texts, contexts, preds, strict=True)}` line using the original `contexts` (it must match `inp.context` in the lookup).

3. `benchmark_configs`: change the signature to

```python
def benchmark_configs(
    configs: dict[str, Any],
    datasets: dict[str, Dataset],
    context_modes: Sequence[Literal["none", "with"]] = ("none", "with"),
) -> pd.DataFrame:
```

Add to its docstring `Args:` and `Returns:`:

```
        context_modes: Which context modes to run per (config, dataset). ``"none"`` classifies the claim text alone;
            ``"with"`` also passes each case's review context and is skipped for datasets that have none.
```
and mention the extra `context` column in `Returns:`.

Replace the `combos` line and the loop header with:

```python
    combos = [
        (cn, dn, clf, ds, mode)
        for cn, clf in configs.items()
        for dn, ds in datasets.items()
        for mode in context_modes
    ]
    for config_name, dataset_name, classifier, dataset, mode in track(combos, description="Benchmarking..."):
        logger.info("Benchmarking '%s' on '%s' (context=%s)", config_name, dataset_name, mode)
```

After the existing `contexts = [...]` line inside the loop add:

```python
        if mode == "with" and not any(contexts):
            logger.info("Skipping context mode 'with' for '%s': dataset has no context", dataset_name)
            continue
        predict_contexts = contexts if mode == "with" else [None] * len(texts)
```

In the prediction `try:` block replace `contexts` with `predict_contexts` in the three prediction uses (`any(contexts) and supports_context`, `classify_batch(texts, contexts=contexts)`, and the sequential branch), renaming the sequential local `use_context` to `pass_context` for consistency. Keep the `cache = {(t, c): p ... zip(texts, contexts, ...)}` line on the original `contexts`.

Add `"context": mode,` to **both** row dicts (the failure row and the success row), right after `"dataset": dataset_name,`.

4. `print_benchmark`: add to `col_spec` after the `("dataset", ...)` entry:

```python
        ("context", "Ctx", "dim", "left", 6, True),
```

and after `_console.print(table)` add:

```python
    if "context" in df.columns and (df["context"] == "with").any():
        _console.print("[dim]Note: gold labels were annotated from claim text only.[/dim]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_eval_context.py -v` then `uv run pytest tests -q`
Expected: PASS everywhere. If `test_prints_claim_only_note...` wraps the note across lines, the test already normalises whitespace; if rich colours break the substring, run with `NO_COLOR=1`.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff check --fix climafactskg tests
uv run ruff format climafactskg tests
git add climafactskg/classifiers/cards/eval.py tests/test_eval_context.py
git commit -m "feat(eval): evaluate with and without review context"
```

---

### Task 5: Docs and live verification

**Files:**
- Modify: `CLAUDE.md` (eval bullet in Architecture, and the test-coverage bullet)
- Modify: `docs/superpowers/specs/2026-09-29-eval-dataset-context-design.md` (deviation note)

- [ ] **Step 1: Update CLAUDE.md**

In the `datasets.py`/`eval.py`/`evaluators.py` bullet, append:

```
Review context for the ClimateSense datasets is prepared by `cards/context.py` (deterministic, LLM-free): `build_climatesense_context("v1"|"v2")` writes a sidecar `cards_annotations_context.csv` next to each consensus CSV (local annotation input CSVs for v2, one CimpleKG `VALUES` query for v1's CimpleKG claims; quotes have no review), and the dataset loaders join it in and run `select_context` (sentence-based, drops claim restatements and verdict fragments, `max_context_chars=800`). `evaluate(..., use_context=False)` is the like-for-like run; `benchmark_configs` runs each dataset with and without context (`context_modes`). The gold labels were annotated from claim text only, so a with-context run measures agreement with claim-only labels, not accuracy against a context-informed truth. The transformer engine slices `text + context` to 256 characters, so context is only meaningful for the LLM engine.
```

In the test-coverage bullet, add `cards/context.py` (selection, sidecar building), the dataset loaders' context join, and `evaluate`/`benchmark_configs` context modes to the covered list, and update the test count to the new total (run `uv run pytest tests -q` and use the reported number).

- [ ] **Step 2: Add the spec deviation note**

Append to the "Design" section of the spec, under component 2:

```
Deviation from the first draft: `build_climatesense_context` lives in `context.py` (with the path constants it needs)
rather than `datasets.py`, to keep `datasets.py` from growing and to avoid an import cycle.
```

- [ ] **Step 3: Full checks**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest tests -q
```
Expected: clean; all tests pass.

- [ ] **Step 4: Live verification (a few cents; needs network, the Google service account, and `OPENROUTER_API_KEY`)**

Build the v2 sidecar (local join, no network) and the v1 sidecar (one CimpleKG query), and look at the coverage and a sample:

```bash
uv run python - <<'EOF'
import pandas as pd
from climafactskg.classifiers.cards.context import build_climatesense_context, select_context
for v in ("v2", "v1"):
    sidecar = build_climatesense_context(v, force=True)
    print(v, len(sidecar), "documents with review context;", sidecar.context_source.value_counts().to_dict())
c = pd.read_csv("data/cards_annotations_v2b/cards_annotations_consensus.csv")
s = build_climatesense_context("v2").merge(c[["document_id", "content"]], on="document_id")
for _, r in s.head(2).iterrows():
    print("\nCLAIM  :", r.content[:100]); print("CONTEXT:", select_context(r.context, r.content))
EOF
```

Expected: v2 reports 277 documents from `input_csv`; v1 reports about 150 from `cimplekg`; samples show sentence-bounded text of at most 800 characters with no `verdict` fragment.

Then run a small with/without comparison with the cheap model and a scratch cache (never the `.env` default model):

```bash
uv run python - <<'EOF'
from climafactskg.classifiers.cards import CARDSLLMClassifier
from climafactskg.classifiers.cards.eval import benchmark_configs, climatesense_dataset_v2, print_benchmark

clf = CARDSLLMClassifier(provider="openrouter", model="openai/gpt-4o-mini", use_preclassifier=False,
                         cache_path="/tmp/context_smoke_cache.db")
ds = climatesense_dataset_v2(limit=20)
print_benchmark(benchmark_configs({"gpt-4o-mini": clf}, {"cs_v2 (20)": ds}), title="Context smoke")
EOF
```

Expected: two rows (`Ctx` = `none` and `with`), 20 cases each, the "claim text only" note printed, and no exception.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-09-29-eval-dataset-context-design.md
git commit -m "docs: document review context for the eval datasets"
```

(Do not commit anything under `data/`; the sidecars are untracked, like the consensus CSVs.)
