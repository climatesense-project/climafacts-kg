import logging

from rdflib import SDO, Graph, Namespace, URIRef
from rdflib.namespace import NamespaceManager
from tinydb import TinyDB

logging.basicConfig(level=logging.INFO)


def generate_cimplekg_mappings(db: TinyDB) -> Graph:
    """Generates RDF mappings from a TinyDB database and returns them as an rdflib Graph.

    This function iterates over all mappings in the provided TinyDB database, and for each mapping with a valid
    'cards_category' (not None and not "0_0"), it creates RDF triples linking the mapping's URL to a category
    namespace using the Schema.org 'about' and 'subjectOf' predicates. The resulting triples are added to an
    rdflib Graph, which is returned.

    Args:
        db (TinyDB): The TinyDB database containing mapping records. Each record is expected to have a 'url'
            and optionally a 'cards_category' field.

    Returns:
        Graph: An rdflib Graph containing the generated RDF mappings.
    Logs:
        - Information about the start and completion of the mapping generation.
        - Success or error messages for each processed mapping.
    """
    logging.info("Starting CimpleKG mapping generation.")
    ns = Namespace("https://purl.net/climafactskg/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)

    for mapping in db.all():
        url = mapping["url"]
        cards_category_id = mapping.get("cards_category", None)

        if cards_category_id != None and cards_category_id != "0_0":  # noqa: E711
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
