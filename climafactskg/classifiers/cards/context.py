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
