import logging
from typing import Optional

import pandas as pd
import preserve
from langdetect import detect
from rich.progress import track

from climafactskg.collectors.utils import batch_classify_cards_category
from climafactskg.utils import query_sparqlendpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CIMPLEKG_SPARQL_ENDPOINT = "https://data.cimple.eu/sparql"
CIMPLEKG_QUERY = """
PREFIX schema: <http://schema.org/>
PREFIX cimple: <http://data.cimple.eu/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?rev ?date_published ?text
WHERE {
    ?rev a schema:ClaimReview;
        schema:inLanguage "English";
        schema:datePublished ?date_published ;
        schema:itemReviewed ?cl .
    ?cl schema:text ?text .
}
ORDER BY DESC(?date_published)
"""


def fetch_claims() -> pd.DataFrame:
    """Fetch claims from the CimpleKG SPARQL endpoint and return as a DataFrame."""
    results = query_sparqlendpoint(CIMPLEKG_SPARQL_ENDPOINT, CIMPLEKG_QUERY)

    # Ensure results is a DataFrame
    if not isinstance(results, pd.DataFrame):
        results = pd.DataFrame(results)

    logger.info(f"Number of results: {len(results)}")
    return results


def process_claims(db: preserve.Connector, claims_df: pd.DataFrame) -> None:
    for _, row in track(claims_df.iterrows(), total=claims_df.shape[0], description="Processing claims"):
        text = row.get("text")

        # Check if URL not already in database
        if row.get("rev") not in db:
            print(f"Processing claim with URL: {row.get('rev')}")
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


def classify_claims(
    db: preserve.Connector,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
) -> None:
    """Classifies claims in the provided database using CARDS classification (batch mode).

    Iterates through claims in the database, optionally filtering by language.
    For each claim that does not already have a 'cards_category' (unless *force* is
    True) and contains a 'claim' text, the function classifies the claim using the
    batch API and updates the database entries with the resulting categories.

    Args:
        db (preserve.Connector): The database connector to access and update claims.
        filter_lang (str, optional): The language code to filter claims. Only claims
            matching this language will be classified. Defaults to "en".
        force (bool, optional): Re-classify claims that already have a
            'cards_category'. Defaults to False.
        concurrency (int, optional): Maximum number of concurrent LLM calls.
            Defaults to the classifier preset's own tuned concurrency. Only used
            when ``classifier_engine="llm"``.
        classifier_engine (str, optional): ``"transformer"`` (default) or ``"llm"``.
            See :func:`batch_classify_cards_category`.

    Returns:
        None
    """
    batch_classify_cards_category(
        db,
        text_field="claim",
        filter_lang=filter_lang,
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        collect_description="Collecting claims to classify",
        save_description="Saving classifications",
        empty_message="No claims to classify.",
        classify_item_name="claims",
    )


def process_all(
    db: preserve.Connector,
    claims_df: pd.DataFrame,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
) -> None:
    """Process all claims data through the complete pipeline.

    This function orchestrates the full claims processing workflow by first
    processing the raw claims data and then classifying the processed claims.

    Args:
        db (preserve.Connector): Database connector instance for data operations.
        claims_df (pd.DataFrame): DataFrame containing the raw claims data to be processed.
        filter_lang (str, optional): Language filter for claim classification. Defaults to "en".
        force (bool, optional): Re-classify already-classified claims. Defaults to False.
        concurrency (int, optional): Maximum concurrent LLM calls. Defaults to the
            classifier preset's own tuned concurrency. Only used when
            ``classifier_engine="llm"``.
        classifier_engine (str, optional): ``"transformer"`` (default) or ``"llm"``.
            See :func:`batch_classify_cards_category`.

    Returns:
        None: This function performs operations in-place and does not return any value.

    Note:
        The function logs progress messages at info level for both processing and
        classification stages.
    """
    logger.info("Processing claims...")
    process_claims(db, claims_df)
    logger.info("Classifying claims...")
    classify_claims(
        db, filter_lang=filter_lang, force=force, concurrency=concurrency, classifier_engine=classifier_engine
    )


if __name__ == "__main__":
    import preserve
    from dotenv import load_dotenv

    load_dotenv()

    with preserve.open(format="sqlite", filename="data/cimplekg_claims_db.db") as db:
        process_all(db, fetch_claims())
