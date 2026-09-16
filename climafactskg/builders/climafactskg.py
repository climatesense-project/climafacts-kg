import logging
import os
import re
import urllib.parse
from typing import Optional

import iso639
import preserve
from dotenv import load_dotenv
from rdflib import OWL, RDF, RDFS, SDO, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import NamespaceManager

from climafactskg.builders.cimplekg import add_cards_category_link, generate_cimplekg_mappings
from climafactskg.utils import hash_string


def _normalize_text(value: str) -> str:
    """Collapse all whitespace runs (including newlines) to a single space.

    rdflib serialises any string containing newlines or double-quotes as a
    triple-quoted Turtle literal. Normalising here keeps every text Literal on one logical line.
    """
    return " ".join(value.split())


# RFC 3986 characters that are safe to leave unencoded in a URI
_URI_SAFE = ":/?#[]@!$&'()*+,;=-._~%"


def _safe_uriref(url: str) -> URIRef:
    """Return a URIRef for *url*, percent-encoding any characters that are illegal in an IRI."""
    return URIRef(urllib.parse.quote(url, safe=_URI_SAFE))


_LEVEL_SUFFIX_RE = re.compile(r"-(basic|intermediate|advanced)(\.htm)$", re.IGNORECASE)


def _canonical_claim_url(url: str) -> str:
    """Strip a difficulty-level suffix from a SkS URL to get the canonical myth URL.

    E.g. ``foo-basic.htm`` → ``foo.htm``, ``foo-advanced.htm`` → ``foo.htm``.
    URLs that don't have such a suffix are returned unchanged.
    """
    return _LEVEL_SUFFIX_RE.sub(r"\2", url)


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
    ns = Namespace("https://purl.net/climatesense/climafactskg/ns#")
    # CARDS concept URIs (cards_category_id below) live in their own namespace,
    # independent of ClimaFactsKG's instance-data namespace — CARDS is a shared
    # taxonomy also used by CimpleKG, not something ClimaFactsKG owns.
    cards_ns = Namespace("https://purl.net/climatesense/cards/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)
    g.namespace_manager.bind("cards", cards_ns)

    # Iterate over all the articles in the database and create RDF triples:
    for _, arg in db:
        url = arg["url"]
        lang = arg["lang"]
        language = iso639.to_name(lang)

        if ignore_urls and url in ignore_urls:
            logging.info(f"Skipping URL (ignored): {url}")
            continue

        logging.info(f"Processing article URL: {url}")
        try:
            claimreview_id = f"claimreview_{hash_string(url)}"

            g.add((ns[claimreview_id], RDF.type, SDO.ClaimReview))
            g.add((ns[claimreview_id], SDO.url, _safe_uriref(url)))

            # Emit educationalLevel and link to canonical ClaimReview for level variants:
            if arg.get("level"):
                g.add((ns[claimreview_id], SDO.educationalLevel, Literal(arg["level"])))
                canonical_cr_id = f"claimreview_{hash_string(arg['main_url'])}"
                if canonical_cr_id != claimreview_id:
                    g.add((ns[claimreview_id], RDFS.seeAlso, ns[canonical_cr_id]))

            # Add rating. BNode id is content-derived (not rdflib's random default)
            # so re-running build on the same data serializes deterministically.
            b = BNode(hash_string(f"rating|{claimreview_id}"))
            g.add((ns[claimreview_id], SDO.reviewRating, b))
            g.add((b, RDF.type, SDO.Rating))
            g.add((b, SDO.ratingValue, Literal(0, datatype=XSD.integer)))
            g.add((b, SDO.bestRating, Literal(1, datatype=XSD.integer)))
            g.add((b, SDO.worstRating, Literal(0, datatype=XSD.integer)))
            g.add(
                (
                    b,
                    SDO.ratingExplanation,
                    Literal(_normalize_text(arg["what_the_science_says"]), lang=lang),
                )
            )
            g.add((b, SDO.name, Literal("False", datatype=SDO.Text)))

            # Add updated date if present:
            if "last_update" in arg and arg["last_update"] is not None:
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.dateCreated,
                        Literal(arg["last_update"], datatype=XSD.date),
                    )
                )

            # Add language information:
            g.add(
                (
                    ns[claimreview_id],
                    SDO.inLanguage,
                    Literal(language),
                )
            )

            # Add author information if present:
            if "author" in arg and arg["author"] is not None:
                author_id = f"person_{hash_string(arg['author'])}"
                g.add((ns[claimreview_id], SDO.author, ns[author_id]))
                g.add((ns[author_id], RDF.type, SDO.Person))
                g.add((ns[author_id], SDO.name, Literal(arg["author"])))

            # Add publisher information:
            g.add((ns[claimreview_id], SDO.publisher, ns["organization_sks"]))
            g.add((ns["organization_sks"], RDF.type, SDO.Organization))
            g.add(
                (
                    ns["organization_sks"],
                    SDO.name,
                    Literal("Skeptical Science"),
                )
            )
            g.add(
                (
                    ns["organization_sks"],
                    SDO.url,
                    URIRef("https://skepticalscience.com"),
                )
            )

            # Add license information:
            g.add(
                (
                    ns[claimreview_id],
                    SDO.license,
                    URIRef("https://creativecommons.org/licenses/by/3.0/"),
                )
            )

            # Add description if present:
            if "description" in arg and arg["description"] is not None:
                g.add(
                    (
                        ns[claimreview_id],
                        SDO.description,
                        Literal(_normalize_text(arg["description"]), lang=lang),
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
                        Literal(_normalize_text(arg["at_glance"]), lang=lang),
                    )
                )

            # Add cards category if present.
            add_cards_category_link(g, cards_ns, ns[claimreview_id], arg.get("cards_category"))

            # Add content of the review:
            g.add((ns[claimreview_id], SDO.name, Literal(_normalize_text(arg["title"]), lang=lang)))
            g.add(
                (
                    ns[claimreview_id],
                    SDO.headline,
                    Literal(_normalize_text(arg["what_the_science_says"]), lang=lang),
                )
            )
            if arg.get("content"):
                g.add((ns[claimreview_id], SDO.reviewBody, Literal(_normalize_text(arg["content"]), lang=lang)))
                g.add((ns[claimreview_id], SDO.text, Literal(_normalize_text(arg["content"]), lang=lang)))

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

            # Link level-variant ClaimReview to the canonical-URL ClaimReview:
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
                        Literal(language["code"]),
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
            # All level variants (basic/intermediate/advanced) of the same myth
            # share one sc:Claim node identified by the canonical (suffix-free) URL.
            canonical_url = _canonical_claim_url(arg["main_url"])
            claim_id = f"claim_{hash_string(canonical_url)}"
            g.add((ns[claimreview_id], SDO.claimReviewed, ns[claim_id]))
            g.add((ns[claim_id], RDF.type, SDO.Claim))
            g.add((ns[claim_id], SDO.text, Literal(_normalize_text(arg["climate_myth"]), lang=lang)))

            # Add the claim source if present:
            if "climate_myth_source" in arg and arg["climate_myth_source"] is not None:
                g.add(
                    (
                        ns[claim_id],
                        SDO.citation,
                        _safe_uriref(arg["climate_myth_source"]["url"]),
                    )
                )

            logging.info(f"Successfully processed article URL: {url}")

        except Exception as e:
            logging.error(f"Error processing article URL {url}: {e}")

    # Citations half done (2026-09-16): sksreferenceskg.py:generate_citations_graph
    # already matches article text against sksTiptionary research-paper entries
    # (citation=="4") and emits schema:citation/cito:cites triples.
    #
    # Definitions half still missing: the other tiptionary entries (IPCC/NSIDC
    # glossary terms, e.g. "radiative forcing") are fetched by
    # collectors/skepticalscience.py:fetch_skstiptionary but discarded —
    # parse_skstiptionary_references() filters to citation=="4" only, so
    # glossary definitions are never stored or linked. Building this out needs:
    # (1) a parser for the non-citation entries (parse_skstiptionary_full()
    #     already gives the raw dict — reuse it, don't re-parse);
    # (2) DB storage for them (new table/db, or extend the references DB with
    #     a type field so SksMatcher's tiptionary dict still covers both);
    # (3) an RDF schema decision for a "term definition" link — schema:DefinedTerm
    #     + schema:description, or skos:Concept + skos:definition;
    # (4) a builder function mirroring generate_citations_graph's per-sentence
    #     SksMatcher.get_matching_keys() loop, emitting the definition triples
    #     instead of citation triples for matched glossary keys.
    # Comparable in scope to the citations feature itself — scope as its own
    # task, not a quick addition here.

    logging.info("Knowledge graph generation completed.")
    return g


def build_climafactskg(
    climafactskg_db: str = "data/skepticalscience_arguments_db.db",
    cards_ttl: str = "data/cards.ttl",
    cimplekg_db: str = "data/cimplekg_claims_db.db",
    climatesensekg_db: Optional[str] = "data/climatesensekg_claims_db.db",
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
        climatesensekg_db (Optional[str]): Path to the ClimateSenseKG claims database. Same entry shape as
            *cimplekg_db* (produced by the same collector code), so it's merged in with the same mapping
            function. Pass ``None`` to skip. Defaults to "data/climatesensekg_claims_db.db".
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

    if climatesensekg_db is not None and os.path.exists(climatesensekg_db):
        logging.info(f"Loading ClimateSenseKG DB from: {climatesensekg_db}")
        # Same entry shape as cimplekg_db (produced by the same collector code),
        # so the mapping function is shared as-is.
        with preserve.open(format="sqlite", filename=climatesensekg_db) as db:
            climatesensekg_g = generate_cimplekg_mappings(db)
            g += climatesensekg_g
    elif climatesensekg_db is not None:
        logging.info(f"ClimateSenseKG DB not found at {climatesensekg_db}, skipping.")

    logging.info("ClimaFactsKG build process completed.")
    return g
