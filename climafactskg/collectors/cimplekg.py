import logging

import pandas as pd
import preserve
from langdetect import detect
from rich.progress import track

from climafactskg.classifiers.cards import CARDSClassifier
from climafactskg.utils import query_sparqlendpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    results = query_sparqlendpoint("https://data.cimple.eu/sparql", CIMPLEKG_QUERY)  # TODO Cache query results.

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


def classify_claims(db: preserve.Connector, filter_lang: str = "en") -> None:
    """Classifies claims in the provided database using the CARDSClassifier.

    Iterates through claims in the database, optionally filtering by language.
    For each claim that does not already have a 'cards_category' and contains a 'claim' text,
    the function classifies the claim and updates the database entry with the resulting category.

    Args:
        db (preserve.Connector): The database connector to access and update claims.
        filter_lang (str, optional): The language code to filter claims. Only claims matching this
            language will be classified. Defaults to "en".

    Returns:
        None
    """
    classifier = CARDSClassifier()
    for url, claim in track(db, description="Classifying claims"):
        if filter_lang and "lang" in claim and claim.get("lang") != filter_lang:
            logger.info(f"Skipping claim with URL {claim.get('url')} due to language mismatch: {claim.get('lang')}")
        else:
            if "cards_category" not in claim and "claim" in claim:
                text = claim["claim"]
                claim["cards_category"] = classifier.classify(text)
                db[url] = claim


def process_all(db: preserve.Connector, claims_df: pd.DataFrame, filter_lang: str = "en") -> None:
    """Process all claims data through the complete pipeline.

    This function orchestrates the full claims processing workflow by first
    processing the raw claims data and then classifying the processed claims.

    Args:
        db (preserve.Connector): Database connector instance for data operations.
        claims_df (pd.DataFrame): DataFrame containing the raw claims data to be processed.
        filter_lang (str, optional): Language filter for claim classification. Defaults to "en".

    Returns:
        None: This function performs operations in-place and does not return any value.

    Note:
        The function logs progress messages at info level for both processing and
        classification stages.
    """
    logger.info("Processing claims...")
    process_claims(db, claims_df)
    logger.info("Classifying claims...")
    classify_claims(db, filter_lang=filter_lang)


if __name__ == "__main__":
    import preserve
    from dotenv import load_dotenv

    load_dotenv()

    with preserve.open(format="sqlite", filename="data/cimplekg_claims_db.db") as db:
        process_all(db, fetch_claims())
