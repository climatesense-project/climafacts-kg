import logging
from typing import Optional

import pandas as pd
import preserve

from climafactskg.collectors.utils import classify_claim_reviews, process_all_claim_reviews, process_claim_reviews
from climafactskg.utils import query_sparqlendpoint

logger = logging.getLogger(__name__)

# Investigated (2026-09-16): the endpoint's general graph has schema:mentions
# <http://dbpedia.org/resource/Climate_change> on ~13k ClaimReviews, which
# could pre-filter this query. Decided not to: it would permanently drop any
# climate claim not tagged with that exact DBpedia entity, silently and
# unrecoverably (no record that it was excluded vs never existed). Classifying
# everything costs more but has no recall risk — keep as-is.
CLIMATESENSEKG_SPARQL_ENDPOINT = "https://climatesense-qlever-server.tools.eurecom.fr/"
CLIMATESENSEKG_QUERY = """
PREFIX schema: <http://schema.org/>
PREFIX cimple: <http://data.cimple.eu/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?rev ?date_published ?text
WHERE {
  {
    SELECT DISTINCT ?rev ?date_published ?g
    WHERE {
      GRAPH ?g {
        ?rev a schema:ClaimReview ;
             schema:inLanguage "English" ;
             schema:datePublished ?date_published .
      }
      FILTER(?g != <http://data.climatesense-project.eu/graph/climate-fever>)
    }
  }

  GRAPH ?g {
    ?rev schema:itemReviewed ?cl .
    ?cl schema:text ?text .
  }
}
ORDER BY DESC(?date_published)
"""


def fetch_claims() -> pd.DataFrame:
    """Fetch claims from the ClimateSenseKG SPARQL endpoint and return as a DataFrame."""
    results = query_sparqlendpoint(CLIMATESENSEKG_SPARQL_ENDPOINT, CLIMATESENSEKG_QUERY)

    # Ensure results is a DataFrame
    if not isinstance(results, pd.DataFrame):
        results = pd.DataFrame(results)

    logger.info(f"Number of results: {len(results)}")
    return results


def process_claims(db: preserve.Connector, claims_df: pd.DataFrame) -> None:
    """Store raw ClimateSenseKG claims into *db*.

    Delegates to the shared claim-review pipeline (see
    :func:`climafactskg.collectors.utils.process_claim_reviews`) —
    ClimateSenseKG's ``rev``/``date_published``/``text`` column shape matches
    that contract.
    """
    process_claim_reviews(db, claims_df)


def classify_claims(
    db: preserve.Connector,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
) -> None:
    """Classify stored ClimateSenseKG claims.

    Delegates to :func:`climafactskg.collectors.utils.classify_claim_reviews`.
    """
    classify_claim_reviews(
        db,
        filter_lang=filter_lang,
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        cache_path=cache_path,
    )


def process_all(
    db: preserve.Connector,
    claims_df: pd.DataFrame,
    filter_lang: str = "en",
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
) -> None:
    """Store then classify a ClimateSenseKG claims DataFrame.

    Delegates to :func:`climafactskg.collectors.utils.process_all_claim_reviews`.
    """
    process_all_claim_reviews(
        db,
        claims_df,
        filter_lang=filter_lang,
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        cache_path=cache_path,
    )


if __name__ == "__main__":
    import preserve
    from dotenv import load_dotenv

    load_dotenv()

    with preserve.open(format="sqlite", filename="data/climatesensekg_claims_db.db") as db:
        process_all(db, fetch_claims(), concurrency=2)
