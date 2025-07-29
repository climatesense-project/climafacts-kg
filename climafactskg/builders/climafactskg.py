import logging
from typing import Optional

import iso639
from dotenv import load_dotenv
from rdflib import OWL, RDF, RDFS, SDO, BNode, Graph, Literal, Namespace
from rdflib.namespace import NamespaceManager
from tinydb import JSONStorage, TinyDB
from tinydb_serialization import SerializationMiddleware
from tinydb_serialization.serializers import DateTimeSerializer

from climafactskg.builders.cimplekg import generate_cimplekg_mappings
from climafactskg.utils import hash_string

logging.basicConfig(level=logging.INFO)


def generate_climafactskg_base(db: TinyDB, ignore_urls: Optional[list] = None) -> Graph:
    """Generates a knowledge graph (KG) in RDF format from the articles stored in a TinyDB database.

    Args:
        db (TinyDB): The TinyDB database instance containing the articles and their metadata.
        ignore_urls (list, optional): A list of URLs to ignore while generating the KG. Defaults to None.

    Returns:
        Graph: An RDFLib Graph object representing the generated knowledge graph.

    Workflow:
        1. Iterates over all articles in the database.
        2. For each article:
            - Adds RDF triples for metadata such as URL, language, author, publisher, license, and content.
            - Handles nested data like related arguments, languages, and claims.
        3. Logs progress and any issues encountered during the process.

    Notes:
        - The function assumes the existence of helper functions like `hash_string`.
        - The generated graph uses the Schema.org (SDO) vocabulary and custom namespaces.

    Raises:
        Any exceptions raised during RDF triple creation or database access will propagate to the caller.

    Returns:
        Graph: The generated RDF graph.
    """
    logging.info("Starting knowledge graph generation.")
    ns = Namespace("https://purl.net/climafactskg/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)

    # Iterate over all the articles in the database and create RDF triples:
    for arg in db.all():
        url = arg["url"]
        lang = arg["lang"]
        language = iso639.to_name(lang)

        if ignore_urls and url in ignore_urls:
            logging.info(f"Skipping URL (ignored): {url}")
            continue

        # TODO Add all the levels instead of the first level
        if "level" in arg and arg["level"] is not None and lang == "en":
            if arg["level"] != arg["levels"][0]["level"]:
                logging.warning(f'Skipping level "{arg["level"]}" for: {url}')
                continue

        logging.info(f"Processing article URL: {url}")
        try:
            claimreview_id = f"claimreview_{hash_string(url)}"

            g.add((ns[claimreview_id], RDF.type, SDO.ClaimReview))
            g.add((ns[claimreview_id], SDO.url, Literal(url, datatype=SDO.URL)))

            # Add rating:
            b = BNode()
            g.add((ns[claimreview_id], SDO.reviewRating, b))
            g.add((b, RDF.type, SDO.Rating))
            g.add((b, SDO.ratingValue, Literal(0, datatype=SDO.Number)))
            g.add((b, SDO.bestRating, Literal(1, datatype=SDO.Number)))
            g.add((b, SDO.worstRating, Literal(0, datatype=SDO.Number)))
            g.add(
                (
                    b,
                    SDO.ratingExplanation,
                    Literal(arg["what_the_science_says"], lang=lang),
                )
            )
            g.add((b, SDO.name, Literal("False", datatype=SDO.Text)))

            # Add updated date if present:
            if "last_update" in arg and arg["last_update"] is not None:
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.dateCreated,
                        Literal(arg["last_update"], datatype=SDO.Date),
                    )
                )

            # Add language information:
            g.add(
                (
                    ns[claimreview_id],
                    SDO.inLanguage,
                    Literal(language, datatype=SDO.Text),
                )
            )

            # Add author information if present:
            if "author" in arg and arg["author"] is not None:
                author_id = f"person_{hash_string(arg['author'])}"
                g.add((ns[claimreview_id], SDO.author, ns[author_id]))
                g.add((ns[author_id], RDF.type, SDO.Person))
                g.add((ns[author_id], SDO.name, Literal(arg["author"], datatype=SDO.Text)))

            # Add publisher information:
            g.add((ns[claimreview_id], SDO.publisher, ns["organization_sks"]))
            g.add((ns["organization_sks"], RDF.type, SDO.Organization))
            g.add(
                (
                    ns["organization_sks"],
                    SDO.name,
                    Literal("Skeptical Science", lang=lang),
                )
            )
            g.add(
                (
                    ns["organization_sks"],
                    SDO.url,
                    Literal("https://skepticalscience.com", datatype=SDO.URL),
                )
            )

            # Add license information:
            g.add(
                (
                    ns[claimreview_id],
                    SDO.license,
                    Literal("https://creativecommons.org/licenses/by/3.0/", datatype=SDO.URL),
                )
            )

            # Add description if present:
            if "description" in arg and arg["description"] is not None:
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.description,
                        Literal(arg["description"], lang=lang),
                    )
                )

            # Add keywords if present:
            if "keywords" in arg and arg["keywords"] is not None:
                for keyword in arg["keywords"]:
                    g.add((ns[claimreview_id], SDO.keywords, Literal(keyword, lang=lang)))

            # Add abstract if at glance is present:
            if "at_glance" in arg and arg["at_glance"] is not None:
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.abstract,
                        Literal(arg["at_glance"], lang=lang),
                    )
                )

            # Add cards category if present:
            if "cards_category" in arg and arg["cards_category"] is not None and arg["cards_category"] != "0_0":
                cards_category_id = arg["cards_category"]
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.about,
                        ns[cards_category_id],
                    )
                )
                g.add((ns[cards_category_id], SDO.subjectOf, ns[claimreview_id]))

            # Add content of the review:
            g.add((ns[claimreview_id], SDO.name, Literal(arg["title"], lang=lang)))
            g.add(
                (
                    ns[claimreview_id],
                    SDO.headline,
                    Literal(arg["what_the_science_says"], lang=lang),
                )
            )
            g.add((ns[claimreview_id], SDO.reviewBody, Literal(arg["content"], lang=lang)))
            g.add((ns[claimreview_id], SDO.text, Literal(arg["content"], lang=lang)))

            # Add related arguments if present:
            if "related_arguments" in arg and arg["related_arguments"] is not None:
                for related_arg in arg["related_arguments"]:
                    related_claimreview_id = f"claimreview_{hash_string(related_arg['url'])}"
                    g.add(
                        (
                            ns[claimreview_id],
                            SDO.associatedClaimReview,
                            ns[related_claimreview_id],
                        )
                    )
                    g.add((ns[claimreview_id], RDFS.seeAlso, ns[related_claimreview_id]))

            # Add main URL if different:
            if arg["main_url"] != url:
                main_claim_review_id = f"claimreview_{hash_string(arg['main_url'])}"
                g.add((ns[claimreview_id], OWL.sameAs, ns[main_claim_review_id]))

            # Create languages:
            for language in arg["languages"]:
                g.add((ns[language["code"]], RDF.type, SDO.Language))
                g.add(
                    (
                        ns[language["code"]],
                        SDO.alternateName,
                        Literal(language["code"], datatype=SDO.Text),
                    )
                )
                g.add(
                    (
                        ns[language["code"]],
                        SDO.name,
                        Literal(language["lang"], lang=lang),
                    )
                )

            # Add the reviewed claim:
            claim_id = f"claimreview_{hash_string(arg['main_url'])}"
            g.add((ns[claimreview_id], SDO.claimReviewed, ns[claim_id]))
            g.add((ns[claim_id], RDF.type, SDO.Claim))
            g.add((ns[claim_id], SDO.text, Literal(arg["climate_myth"], lang=lang)))

            # Add the claim source if present:
            if "climate_myth_source" in arg and arg["climate_myth_source"] is not None:
                g.add(
                    (
                        ns[claim_id],
                        SDO.citation,
                        Literal(arg["climate_myth_source"]["url"], datatype=SDO.URL),
                    )
                )

            logging.info(f"Successfully processed article URL: {url}")

        except Exception as e:
            logging.error(f"Error processing article URL {url}: {e}")

    # TODO: Cross ref definitions and citations:
    # https://skepticalscience.com/public/assets/jsgen/skstiptionary_1752342798469.js
    # This file contains all the citations and definitions used across the website.

    logging.info("Knowledge graph generation completed.")
    return g


def build_climafactskg(
    climafactskg_db: str = "data/skepticalscience_arguments_db.json",
    cards_ttl: str = "data/cards.ttl",
    cimplekg_db: str = "data/cimplekg_claims_db.json",
    ignore_urls: Optional[list] = None,
) -> Graph:
    """Builds the ClimaFacts Knowledge Graph by integrating data from multiple sources.

    This function loads data from a Skeptical Science JSON database, parses additional CARDS data from a Turtle file,
    and incorporates mappings from a CimpleKG JSON database. The resulting RDF graph combines these sources, optionally
    ignoring specified URLs.

    Args:
        climafactskg_db (str): Path to the Skeptical Science arguments JSON database.
            Defaults to "data/skepticalscience_arguments_db.json".
        cards_ttl (str): Path to the Turtle (.ttl) file containing CARDS data. Defaults to "data/cards.ttl".
        cimplekg_db (str): Path to the CimpleKG claims JSON database. Defaults to "data/cimplekg_claims_db.json".
        ignore_urls (Optional[list]): List of URLs to ignore when building the graph. Defaults to None.

    Returns:
        Graph: An RDFLib Graph object containing the integrated knowledge graph.
    """
    load_dotenv()
    serialization = SerializationMiddleware(JSONStorage)
    serialization.register_serializer(DateTimeSerializer(), "TinyDate")

    logging.info("Starting ClimaFactsKG build process.")

    g = Graph()

    if ignore_urls is None:
        ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    logging.info(f"Loading ClimaFactsKG DB from: {climafactskg_db}")
    with TinyDB(climafactskg_db, storage=serialization) as db:
        db.default_table_name = "arguments"
        g = generate_climafactskg_base(
            db,
            ignore_urls=ignore_urls,
        )
    logging.info(f"Parsing CARDS Turtle file: {cards_ttl}")
    cards_g = Graph()
    cards_g.parse(cards_ttl, format="ttl", encoding="utf-8")
    g += cards_g

    logging.info(f"Loading CimpleKG DB from: {cimplekg_db}")
    # add existing CimpleKG to g:
    with TinyDB(cimplekg_db, storage=serialization) as db:
        db.default_table_name = "mappings"
        cimplekg_g = generate_cimplekg_mappings(db)
        g += cimplekg_g

    logging.info("ClimaFactsKG build process completed.")
    return g
