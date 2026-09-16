import logging
from typing import Optional

import pandas as pd
import preserve
from langdetect import detect
from rich.progress import track

logger = logging.getLogger(__name__)

# Provenance tag for the legacy two-stage transformer classifier (CARDSClassifier),
# matching the value backfilled onto pre-refactor cards_category entries. Keeping
# this as the `process` default for now — switching to the LLM classifier is a
# deliberate later step, not implicit in this reprocessing pass.
TRANSFORMER_CLASSIFIER_ID = "transformer:crarojasca/BinaryAugmentedCARDS,crarojasca/TaxonomyAugmentedCARDS"

# "Not climate misinformation" sentinels used inconsistently across engines
# (transformer/matcher: "0"; LLM: "0_0" — see taxonomy.py, both are valid
# taxonomy nodes and evaluators.py already normalises between them for
# scoring). Checking both here is what lets `is_climate_related` be derived
# uniformly regardless of which engine produced the category.
NOT_RELATED_CATEGORIES = frozenset({"0", "0_0"})


def batch_classify_cards_category(
    db: preserve.Connector,
    *,
    text_field: str,
    force: bool = False,
    filter_lang: Optional[str] = "en",
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cards_classifier_name: str = "xplainnlp-nslp",
    cache_path: Optional[str] = None,
    collect_description: str = "Collecting items to classify",
    save_description: str = "Saving classifications",
    empty_message: str = "No items to classify.",
    classify_item_name: str = "items",
) -> None:
    """Batch-classify DB entries and store CARDS category fields.

    Entries are filtered by language and existing classification (unless *force*).
    The function classifies all pending texts in one batch call and then saves
    ``cards_category``, ``cards_category_classifier``, and ``is_climate_related``
    (derived from ``cards_category not in NOT_RELATED_CATEGORIES`` — true for
    either engine's "not related" sentinel, ``"0"`` or ``"0_0"``) to each entry.

    Args:
        db: Database connector to read pending entries from and write results to.
        text_field: Name of the entry field holding the text to classify.
        force: Re-classify entries that already carry both ``cards_category`` and
            ``cards_category_classifier``.
        filter_lang: Only classify entries whose ``lang`` field matches this value
            (when present). Entries with a different language have any existing
            ``cards_category`` cleared. Pass ``None`` to disable language filtering.
        concurrency: Maximum number of concurrent LLM calls. Only used when
            ``classifier_engine="llm"``; ignored for ``"transformer"``.
        classifier_engine: ``"transformer"`` (default — the legacy two-stage
            ClimateBERT + taxonomy model, matching pre-refactor behavior, no
            API cost) or ``"llm"`` (the newer LLM-based classifier, named by
            *cards_classifier_name*). Recorded verbatim-equivalent in each
            entry's ``cards_category_classifier`` so a later switch is visible
            and doesn't silently reclassify entries tagged with the other engine.
        cards_classifier_name: Named LLM preset to use. Only used when
            ``classifier_engine="llm"``.
        cache_path: Path to a Preserve SQLite cache shared across calls and,
            when the same path is passed by multiple collector sources, across
            sources too — identical claim text classified once instead of once
            per source. ``None`` (default) disables caching.
        collect_description: Progress-bar label for the collection pass.
        save_description: Progress-bar label for the save pass.
        empty_message: Log message when there are no pending entries.
        classify_item_name: Noun used in log messages (e.g. "claims", "arguments").

    Note: an entry is only treated as "already classified" (and skipped) once it
    carries *both* ``cards_category`` and ``cards_category_classifier``. Entries
    labeled by an earlier, different classifier — i.e. ``cards_category`` present
    but ``cards_category_classifier`` absent — are treated as pending and will be
    reclassified here even without ``force=True``. The first run after switching
    classifiers will therefore reclassify every pre-existing legacy-labeled entry,
    not just genuinely new ones; subsequent runs are cheap once the provenance
    field is backfilled.
    """
    if classifier_engine == "transformer":
        from climafactskg.classifiers.cards import CARDSClassifier

        classifier = CARDSClassifier(cache_path=cache_path)
        classifier_id = TRANSFORMER_CLASSIFIER_ID
    elif classifier_engine == "llm":
        from climafactskg.classifiers.cards.llm import CARDSLLMClassifier

        overrides = {"cache_path": cache_path} if cache_path is not None else {}
        classifier = CARDSLLMClassifier.from_preset(cards_classifier_name, **overrides)
        classifier_id = cards_classifier_name
    else:
        raise ValueError(f"Unknown classifier_engine {classifier_engine!r}; expected 'transformer' or 'llm'")

    pending_urls: list[str] = []
    pending_entries: list[dict] = []
    pending_texts: list[str] = []

    for url, entry in track(db, description=collect_description):
        if filter_lang and "lang" in entry and entry.get("lang") != filter_lang:
            if entry.get("cards_category") is not None:
                entry["cards_category"] = None
                db[url] = entry
            continue
        if not force and "cards_category" in entry and "cards_category_classifier" in entry:
            continue
        text_value = entry.get(text_field)
        if not text_value:
            continue

        pending_urls.append(url)
        pending_entries.append(entry)
        pending_texts.append(text_value)

    if not pending_texts:
        logger.info(empty_message)
        return

    if classifier_engine == "transformer":
        logger.info(f"Classifying {len(pending_texts)} {classify_item_name} (engine=transformer)...")
        categories = classifier.classify_batch(pending_texts)
    else:
        concurrency_desc = concurrency if concurrency is not None else "preset default"
        logger.info(f"Classifying {len(pending_texts)} {classify_item_name} (concurrency={concurrency_desc})...")
        categories = classifier.classify_batch(pending_texts, concurrency=concurrency)

    failed = 0
    for url, entry, category in track(
        zip(pending_urls, pending_entries, categories),
        total=len(pending_urls),
        description=save_description,
    ):
        if category is None:
            failed += 1
            continue
        entry["cards_category"] = category
        entry["cards_category_classifier"] = classifier_id
        entry["is_climate_related"] = category not in NOT_RELATED_CATEGORIES
        db[url] = entry

    if failed:
        logger.warning(
            f"{failed}/{len(pending_urls)} {classify_item_name} failed to classify and remain pending for retry."
        )


# ── Shared claim-review collector pipeline ───────────────────────────────────
#
# CimpleKG and ClimateSenseKG are both SPARQL-backed ClaimReview sources whose
# queries happen to alias columns identically (rev/date_published/text). That
# contract is declared explicitly here, once, instead of one collector module
# silently importing another's internals (which is what happened before: see
# git history on collectors/climatesensekg.py). Any new SPARQL ClaimReview
# source can reuse these directly as long as its `fetch_claims()` DataFrame
# has the same three columns; if it can't, write its own `process_claims`
# rather than forcing the shape to fit.


def process_claim_reviews(db: preserve.Connector, claims_df: pd.DataFrame) -> None:
    """Store raw ClaimReview rows into *db*, skipping URLs already present.

    Args:
        db: Database connector to write new claims into.
        claims_df: Must have ``rev`` (claim URL), ``date_published``, and
            ``text`` columns — the shape produced by both the CimpleKG and
            ClimateSenseKG SPARQL queries.
    """
    for _, row in track(claims_df.iterrows(), total=claims_df.shape[0], description="Processing claims"):
        text = row.get("text")

        if row.get("rev") not in db:
            if isinstance(text, str) and text.strip():
                lang = None
                try:
                    lang = detect(text)
                except Exception as e:
                    logger.warning(f"Language detection failed for text: {text[:30]}... Error: {e}")
                mapping = {
                    "url": row.get("rev"),
                    "date_published": row.get("date_published"),
                    "claim": text,
                    "lang": lang,
                }
                db[mapping["url"]] = mapping
        else:
            logger.info(f"Skipping already processed claim with URL: {row.get('rev')}")


def classify_claim_reviews(
    db: preserve.Connector,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
) -> None:
    """Classifies stored ClaimReview entries using CARDS classification (batch mode).

    Thin wrapper around :func:`batch_classify_cards_category` fixed to the
    ``claim`` text field used by :func:`process_claim_reviews`. See that
    function's docstring for the full parameter reference.
    """
    batch_classify_cards_category(
        db,
        text_field="claim",
        filter_lang=filter_lang,
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        cache_path=cache_path,
        collect_description="Collecting claims to classify",
        save_description="Saving classifications",
        empty_message="No claims to classify.",
        classify_item_name="claims",
    )


def process_all_claim_reviews(
    db: preserve.Connector,
    claims_df: pd.DataFrame,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
) -> None:
    """Store then classify a ClaimReview DataFrame.

    See :func:`process_claim_reviews` and :func:`classify_claim_reviews` for
    the two stages this runs in order.
    """
    logger.info("Processing claims...")
    process_claim_reviews(db, claims_df)
    logger.info("Classifying claims...")
    classify_claim_reviews(
        db,
        filter_lang=filter_lang,
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        cache_path=cache_path,
    )
