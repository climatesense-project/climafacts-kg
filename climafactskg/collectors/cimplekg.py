import logging

import pandas as pd
from langdetect import detect
from rich.progress import track
from tinydb import TinyDB, where

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
LIMIT 100
"""


def fetch_claims() -> pd.DataFrame:
    """Fetch claims from the CimpleKG SPARQL endpoint and return as a DataFrame."""
    results = query_sparqlendpoint("https://data.cimple.eu/sparql", CIMPLEKG_QUERY)  # TODO Cache query results.

    # Ensure results is a DataFrame
    if not isinstance(results, pd.DataFrame):
        results = pd.DataFrame(results)

    logger.info(f"Number of results: {len(results)}")
    return results


def process_claims(db: TinyDB, claims_df: pd.DataFrame) -> None:
    for _, row in track(claims_df.iterrows(), total=claims_df.shape[0], description="Processing claims"):
        text = row.get("text")

        # Check if URL not already in database
        if not db.contains(where("url") == row.get("rev")):
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
                db.insert(mapping)
        else:
            logger.info(f"Skipping already processed claim with URL: {row.get('rev')}")


def classify_claims(db: TinyDB, filter_lang: str = "en") -> None:
    """Classifies claims in the TinyDB database using the CARDSClassifier.

    This function iterates over all claims in the provided TinyDB instance.
    - If a claim does not have a "cards_category", it uses the CARDSClassifier to predict a category
        for the "claim" text and updates the claim with this prediction.

    Args:
        db (TinyDB): The TinyDB database instance containing claims to classify.
        filter_lang (str): Language code to filter claims for classification (default is "en").

    Returns:
        None
    """
    classifier = CARDSClassifier()

    if filter_lang:
        sel = db.search(where("lang") == filter_lang)
        logger.info(f"Classifying {len(sel)} claims in language '{filter_lang}'")
    else:
        logger.info("Classifying all claims in the database")
        sel = db.all()

    for claim in track(sel, description="Classifying claims"):
        if "cards_category" not in claim and "claim" in claim:
            text = claim["claim"]
            prediction = classifier.classify(text)
            db.update({"cards_category": prediction}, doc_ids=[claim.doc_id])


def process_all(db: TinyDB, claims_df: pd.DataFrame, filter_lang: str = "en") -> None:
    """Fetches claims from CimpleKG, processes them, and stores them in the TinyDB database.

    Args:
        db (TinyDB): The TinyDB database instance where claims will be stored.
        claims_df (pd.DataFrame): DataFrame containing claims to be processed.
        filter_lang (str): Language code to filter claims for classification (default is "en").

    Returns:
        None
    """
    logger.info("Processing claims...")
    process_claims(db, claims_df)
    logger.info("Classifying claims...")
    classify_claims(db, filter_lang=filter_lang)


if __name__ == "__main__":
    from dotenv import load_dotenv
    from tinydb import JSONStorage
    from tinydb_serialization import SerializationMiddleware
    from tinydb_serialization.serializers import DateTimeSerializer

    load_dotenv()
    serialization = SerializationMiddleware(JSONStorage)
    serialization.register_serializer(DateTimeSerializer(), "TinyDate")

    with TinyDB("data/cimplekg_claims_db.json", storage=serialization) as db:
        db.default_table_name = "mappings"
        process_all(db, fetch_claims())
