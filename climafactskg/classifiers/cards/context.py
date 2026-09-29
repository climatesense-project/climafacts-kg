"""Deterministic, LLM-free preparation of fact-check review context for the CARDS eval datasets.

Selecting and cleaning context uses only regexes, word overlap and a character budget, so a with-context eval is
reproducible and free. The one network access (in :func:`fetch_cimplekg_reviews`) is a plain SPARQL fetch of review
text.
"""

import logging
import os
import re
import time
import urllib.error
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


def _is_cimplekg_review_uri(document_id: str) -> bool:
    return document_id.startswith(CIMPLEKG_REVIEW_PREFIX) and bool(_SAFE_URI_RE.match(document_id))


def load_input_reviews(csv_path: str) -> dict[str, str]:
    """Loads ``id -> review`` from an annotation input CSV (columns ``id``, ``review``); blank reviews are skipped."""
    df = pd.read_csv(csv_path, usecols=["id", "review"], encoding="utf-8-sig").dropna()
    return {
        str(doc_id): str(review) for doc_id, review in zip(df["id"], df["review"], strict=True) if str(review).strip()
    }


_RETRYABLE_HTTP_CODES = frozenset({429, 502, 503, 504})


def _query_with_retry(
    query_fn: Callable,
    endpoint: str,
    query: str,
    retries: int,
    backoff_s: float,
    sleep_fn: Callable[[float], None],
):
    """Runs ``query_fn(endpoint, query)``, retrying rate-limit and transient server errors with backoff."""
    for attempt in range(retries + 1):
        try:
            return query_fn(endpoint, query)
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP_CODES or attempt == retries:
                raise
            logger.warning("CimpleKG returned HTTP %s; retrying (%d/%d)", exc.code, attempt + 1, retries)
            sleep_fn(backoff_s * 2**attempt)


def fetch_cimplekg_reviews(
    uris: Iterable[str],
    *,
    endpoint: str = CIMPLEKG_SPARQL_ENDPOINT,
    chunk_size: int = 20,
    query_fn: Callable = query_sparqlendpoint,
    pause_s: float = 1.0,
    retries: int = 3,
    backoff_s: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    """Fetches ``schema:text`` (the review text) for CimpleKG ClaimReview URIs, chunked into ``VALUES`` queries.

    Args:
        uris: ClaimReview URIs. Duplicates are collapsed.
        endpoint: SPARQL endpoint URL.
        chunk_size: URIs per query. Kept small because the query is sent via GET and the endpoint rejects URLs of
            about 8 KB or more (HTTP 414).
        query_fn: ``(endpoint, query) -> DataFrame`` with columns ``rev`` and ``text``; injectable for tests.
        pause_s: Seconds to wait between chunk queries, to stay under the endpoint's rate limit.
        retries: Extra attempts per chunk on HTTP 429/5xx, with exponential backoff (``backoff_s * 2**attempt``).
        backoff_s: Base backoff in seconds.
        sleep_fn: Sleep function; injectable for tests.

    Returns:
        ``uri -> review text``. URIs without a non-blank ``schema:text`` are absent. Endpoint errors propagate.
    """
    unique = list(dict.fromkeys(uris))
    reviews: dict[str, str] = {}
    for start in range(0, len(unique), chunk_size):
        if start:
            sleep_fn(pause_s)
        values = " ".join(f"<{uri}>" for uri in unique[start : start + chunk_size])
        query = (
            "PREFIX schema: <http://schema.org/> "
            f"SELECT ?rev ?text WHERE {{ VALUES ?rev {{ {values} }} ?rev schema:text ?text }}"
        )
        df = _query_with_retry(query_fn, endpoint, query, retries, backoff_s, sleep_fn)
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
