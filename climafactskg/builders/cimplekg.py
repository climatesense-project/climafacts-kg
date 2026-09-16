import logging
from typing import Optional

import preserve
from rdflib import SDO, Graph, Namespace, URIRef
from rdflib.namespace import NamespaceManager

# Both engines have their own "not related" sentinel: "0" for transformer/
# matcher, "0_0" for LLM (see taxonomy.py — both are real taxonomy nodes
# meaning "not climate misinformation or related"). Neither should produce a
# CARDS category link.
NOT_RELATED_CARDS_CATEGORIES = frozenset({"0", "0_0"})


def add_cards_category_link(g: Graph, cards_ns: Namespace, subject: URIRef, cards_category: Optional[str]) -> bool:
    """Adds SDO.about/SDO.subjectOf triples linking *subject* to its CARDS category.

    Shared by every builder that stores a ``cards_category`` field (SkS
    arguments, CimpleKG/ClimateSenseKG mappings) so the not-related sentinel
    exclusion can't drift between them again — see the bug this replaced,
    where climafactskg.py excluded only "0_0" while this module already
    excluded both.

    Args:
        g: Graph to add triples to.
        cards_ns: Namespace the CARDS taxonomy concepts live in.
        subject: The URI (ClaimReview, claim, etc.) the category applies to.
        cards_category: The stored category value, or ``None``.

    Returns:
        True if a link was added (i.e. *cards_category* is a real category,
        not ``None`` or one of :data:`NOT_RELATED_CARDS_CATEGORIES`).
    """
    if cards_category is None or cards_category in NOT_RELATED_CARDS_CATEGORIES:
        return False
    g.add((subject, SDO.about, cards_ns[cards_category]))
    g.add((cards_ns[cards_category], SDO.subjectOf, subject))
    return True


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
    # CARDS concept URIs live in their own namespace, separate from ClimaFactsKG's
    # instance-data namespace — see builders/climafactskg.py for the split rationale.
    ns = Namespace("https://purl.net/climatesense/cards/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("cards", ns)

    for _, mapping in db:
        url = mapping["url"]
        try:
            if add_cards_category_link(g, ns, URIRef(url), mapping.get("cards_category")):
                logging.info(f"Successfully processed CimpleKG URL: {url}")
        except Exception as e:
            logging.error(f"Error processing mapping URL {url}: {e}")

    logging.info("CimpleKG mappings generation completed.")
    return g
