import logging

import preserve
from rdflib import SDO, Graph, Namespace, URIRef
from rdflib.namespace import NamespaceManager

logging.basicConfig(level=logging.INFO)


def generate_cimplekg_mappings(db: preserve.Connector) -> Graph:
    """Generates RDF mappings for CimpleKG from a database connector.

    Iterates over mappings retrieved from the provided database connector, and for each mapping with a valid
    'cards_category' identifier, adds RDF triples to the graph linking the mapping URL to its category using
    schema.org predicates. Logs progress and errors during processing.

    Args:
        db (preserve.Connector): Database connector yielding mappings as dictionaries with 'url' and 'cards_category'.

    Returns:
        Graph: An RDFLib Graph containing the generated CimpleKG mappings.
    """
    logging.info("Starting CimpleKG mapping generation.")
    ns = Namespace("https://purl.net/climafactskg/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)

    for _, mapping in db:
        url = mapping["url"]
        cards_category_id = mapping.get("cards_category", None)

        if cards_category_id != None and cards_category_id != "0" and cards_category_id != "0_0":  # noqa: E711
            try:
                g.add(
                    (
                        URIRef(url),
                        SDO.about,
                        ns[cards_category_id],
                    )
                )
                g.add((ns[cards_category_id], SDO.subjectOf, URIRef(url)))

                logging.info(f"Successfully processed CimpleKG URL: {url}")

            except Exception as e:
                logging.error(f"Error processing mapping URL {url}: {e}")

    logging.info("CimpleKG mappings generation completed.")
    return g
