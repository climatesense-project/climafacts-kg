import logging
from typing import Optional

import iso639
import preserve
from dotenv import load_dotenv
from rdflib import OWL, RDF, RDFS, SDO, BNode, Graph, Literal, Namespace
from rdflib.namespace import NamespaceManager

from climafactskg.builders.cimplekg import generate_cimplekg_mappings
from climafactskg.utils import hash_string

logging.basicConfig(level=logging.INFO)


def generate_climafactskg_base(db: preserve.Connector, ignore_urls: Optional[list] = None) -> Graph:
    """Generates the base knowledge graph for ClimafactsKG from a database of articles.

    This function iterates over articles in the provided database connector, extracting relevant metadata
    and content to construct RDF triples according to the Schema.org vocabulary. The resulting graph
    represents claim reviews, claims, authors, publishers, ratings, and other related entities.

    Args:
        db (preserve.Connector): A database connector yielding article records as dictionaries.
        ignore_urls (Optional[list], optional): A list of URLs to skip during graph generation. Defaults to None.

    Returns:
        Graph: An RDFLib Graph object containing the generated knowledge graph.

    The function performs the following steps for each article:
        - Skips articles whose URLs are in the ignore list.
        - Processes only the first level for English articles.
        - Adds claim review information, including ratings, explanations, and review body.
        - Adds metadata such as author, publisher, license, description, keywords, abstract, and categories.
        - Links related arguments and main URLs.
        - Creates language entities for each supported language.
        - Adds the reviewed claim and its source citation if available.
        - Logs progress and errors during processing.

    Raises:
        Exception: Logs any exceptions encountered during article processing.
    """
    logging.info("Starting knowledge graph generation.")
    ns = Namespace("https://purl.net/climafactskg/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)

    # Iterate over all the articles in the database and create RDF triples:
    for _, arg in db:
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
    climafactskg_db: str = "data/skepticalscience_arguments_db.db",
    cards_ttl: str = "data/cards.ttl",
    cimplekg_db: str = "data/cimplekg_claims_db.db",
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

    logging.info("Starting ClimaFactsKG build process.")

    g = Graph()

    if ignore_urls is None:
        ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    logging.info(f"Loading ClimaFactsKG DB from: {climafactskg_db}")
    with preserve.open(format="sqlite", filename=climafactskg_db) as db:
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
    with preserve.open(format="sqlite", filename=cimplekg_db) as db:
        cimplekg_g = generate_cimplekg_mappings(db)
        g += cimplekg_g

    logging.info("ClimaFactsKG build process completed.")
    return g
