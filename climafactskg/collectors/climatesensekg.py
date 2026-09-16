import logging

import pandas as pd
import preserve

from climafactskg.collectors.cimplekg import process_all
from climafactskg.utils import query_sparqlendpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TODO Filter on climate relatedness in SPARQL query to avoid classifying non-climate claims.
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


if __name__ == "__main__":
    import preserve
    from dotenv import load_dotenv

    load_dotenv()

    with preserve.open(format="sqlite", filename="data/climatesensekg_claims_db.db") as db:
        process_all(db, fetch_claims(), concurrency=2)
