import logging
from typing import Optional

import preserve
from rich.progress import track

logger = logging.getLogger(__name__)

# Provenance tag for the legacy two-stage transformer classifier (CARDSClassifier),
# matching the value backfilled onto pre-refactor cards_category entries. Keeping
# this as the `process` default for now — switching to the LLM classifier is a
# deliberate later step, not implicit in this reprocessing pass.
TRANSFORMER_CLASSIFIER_ID = "transformer:crarojasca/BinaryAugmentedCARDS,crarojasca/TaxonomyAugmentedCARDS"


def batch_classify_cards_category(
    db: preserve.Connector,
    *,
    text_field: str,
    force: bool = False,
    filter_lang: Optional[str] = "en",
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cards_classifier_name: str = "xplainnlp-nslp",
    collect_description: str = "Collecting items to classify",
    save_description: str = "Saving classifications",
    empty_message: str = "No items to classify.",
    classify_item_name: str = "items",
) -> None:
    """Batch-classify DB entries and store CARDS category fields.

    Entries are filtered by language and existing classification (unless *force*).
    The function classifies all pending texts in one batch call and then saves
    both cards_category and cards_category_classifier to each corresponding entry.

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

        classifier = CARDSClassifier()
        classifier_id = TRANSFORMER_CLASSIFIER_ID
    elif classifier_engine == "llm":
        from climafactskg.classifiers.cards.llm import CARDSLLMClassifier

        classifier = CARDSLLMClassifier.from_preset(cards_classifier_name)
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
        db[url] = entry

    if failed:
        logger.warning(
            f"{failed}/{len(pending_urls)} {classify_item_name} failed to classify and remain pending for retry."
        )
