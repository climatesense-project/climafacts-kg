"""Builder that maps SkepticalScience sksTiptionary references to an RDF graph.

Primary vocabulary : Schema.org (ScholarlyArticle, Periodical,
                     PublicationVolume, PublicationIssue, PropertyValue).
Supplementary      : BIBO — bibo:AcademicArticle, bibo:Journal, bibo:doi,
                       bibo:volume, bibo:issue, bibo:pageStart, bibo:pageEnd.
                     CiTO — cito:citesAsEvidence, linking the Skeptical
                       Science website as citing entity to each article.
"""

import logging
import re
from urllib.parse import quote

import preserve
from rdflib import RDF, SDO, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import NamespaceManager

from climafactskg.utils import hash_string

logging.basicConfig(level=logging.INFO)

BIBO = Namespace("http://purl.org/ontology/bibo/")
CITO = Namespace("http://purl.org/spar/cito/")

_DOI_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)

# Strip "et al." / "..." truncation markers and trailing non-author text
_ET_AL_RE = re.compile(r",?\s*(?:\.{3}|et al\.?)\s*", re.IGNORECASE)
_TRAILING_TEXT_RE = re.compile(r'[\xa0\s]*["\u201c].+$', re.DOTALL)


def _split_authors(authors_raw: str) -> list[str]:
    """Split an APA-style author string into individual author name tokens.

    Handles the most common formats found in Skeptical Science references:
    - ``Last, F., Last, F. M., & Last, F.`` (standard APA)
    - ``Last, F.F., Last, F.`` (initials without spaces)
    - et al. / ``...`` truncation markers
    - ``and`` as a separator alternative to ``&``
    - lowercase prefixes such as ``van``, ``de``, ``von``

    Splits on any comma that is immediately preceded by ``[A-Z].`` (the last
    initial of an author entry).  Single-author strings are returned as-is.
    """
    s = _TRAILING_TEXT_RE.sub("", authors_raw)
    s = _ET_AL_RE.sub("", s)
    # Normalise separators: ", & " / " & " / " and " → ", "
    s = re.sub(r",?\s*(?:&|and)\s+", ", ", s)
    s = s.strip().rstrip(",")
    # Split after [Capital][.] immediately before a comma — the end of an initial
    parts = re.split(r"(?<=[A-Z]\.),\s*", s)
    return [p.strip() for p in parts if p.strip()]


def _canonical_doi(doi_field: str) -> tuple[str, str] | None:
    """Return ``(canonical_https_uri, bare_doi)`` from a raw DOI field value.

    Returns ``None`` if the value does not look like a valid DOI (i.e. the
    bare identifier does not start with ``10.``).
    """
    bare = _DOI_PREFIX_RE.sub("", doi_field.strip())
    if not re.match(r"^10\.\d{4,}/", bare):
        logging.warning("Skipping invalid DOI field: %r", doi_field)
        return None
    # Percent-encode characters that are illegal in URIs (e.g. < > { } | \ ^ `)
    # but preserve the slash separating the registrant from the suffix.
    encoded = quote(bare, safe="/:@!$&'()*+,;=-._~")
    return f"https://doi.org/{encoded}", bare


def _split_pages(pages: str) -> tuple[str | None, str | None]:
    """Split a page range such as ``3466-3468`` or ``3466\u20133468`` into ``(start, end)``.

    Returns ``(pages, None)`` when no range separator is found.
    """
    m = re.match(r"^([\w]+)[-\u2013]([\w]+)$", pages)
    if m:
        return m.group(1), m.group(2)
    return pages, None


def generate_references_graph(db: preserve.Connector) -> Graph:
    """Generate an RDF graph of scholarly article references.

    Iterates over reference records produced by
    ``climafactskg.collectors.skepticalscience.process_skstiptionary`` and
    builds RDF triples for each one.  The graph uses Schema.org as the primary
    vocabulary, supplemented by BIBO for flat bibliographic properties and CiTO
    to express that Skeptical Science cites each article as evidence.

    Args:
        db (preserve.Connector): Database connector yielding reference dicts
            as stored by ``process_skstiptionary``.

    Returns:
        Graph: RDFLib Graph containing the generated reference triples.
    """
    logging.info("Starting references graph generation.")
    ns = Namespace("https://purl.net/climatesense/climafactskg/ns#")

    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    g.namespace_manager.bind("", ns)
    g.namespace_manager.bind("bibo", BIBO)
    g.namespace_manager.bind("cito", CITO)

    # SkepticalScience as the citing organization (reused across all entries)
    sks_uri = ns["organization_sks"]
    g.add((sks_uri, RDF.type, SDO.Organization))
    g.add((sks_uri, SDO.name, Literal("Skeptical Science")))
    g.add((sks_uri, SDO.url, URIRef("https://skepticalscience.com")))

    for _, ref in db:
        key = ref.get("key", "").strip()
        try:
            article_uri = ns[f"article_{hash_string(key.lower())}"]

            g.add((article_uri, RDF.type, SDO.ScholarlyArticle))
            g.add((article_uri, RDF.type, BIBO.AcademicArticle))

            if key:
                g.add((article_uri, SDO.alternateName, Literal(key.strip())))

            # Additional citation keys used by SkepticalScience for matching
            for alt_key in ref.get("altKeys") or []:
                # Guard against stray dict objects (e.g. {key: {xmatchtype: …}})
                if isinstance(alt_key, dict):
                    for k in alt_key:
                        k = str(k).strip()
                        if k and k != key:
                            g.add((article_uri, SDO.alternateName, Literal(k)))
                    continue
                alt_key = str(alt_key).strip()
                if alt_key and alt_key != key:
                    g.add((article_uri, SDO.alternateName, Literal(alt_key)))

            if ref.get("title"):
                g.add((article_uri, SDO.name, Literal(ref["title"])))

            # Year — kept as a plain literal to allow "2012a"-style suffixes
            if ref.get("year"):
                g.add((article_uri, SDO.datePublished, Literal(ref["year"])))

            # Authors — split into individual schema:Person nodes
            if ref.get("authors_raw"):
                for author_name in _split_authors(ref["authors_raw"]):
                    b = BNode()
                    g.add((article_uri, SDO.author, b))
                    g.add((b, RDF.type, SDO.Person))
                    g.add((b, SDO.name, Literal(author_name)))

            # Link to paper / PDF / abstract
            if ref.get("url"):
                g.add((article_uri, SDO.url, URIRef(quote(ref["url"], safe=":/?#[]@!$&'()*+,;=-._~%"))))

            # DOI — canonical URI via sameAs, PropertyValue identifier, and bibo:doi
            if ref.get("doi"):
                _doi_result = _canonical_doi(ref["doi"])
                if _doi_result is not None:
                    doi_uri, bare_doi = _doi_result
                    g.add((article_uri, SDO.sameAs, URIRef(doi_uri)))
                    b = BNode()
                    g.add((article_uri, SDO.identifier, b))
                    g.add((b, RDF.type, SDO.PropertyValue))
                    g.add((b, SDO.propertyID, Literal("doi")))
                    g.add((b, SDO.value, Literal(bare_doi)))
                    g.add((article_uri, BIBO.doi, Literal(bare_doi)))

            # Pages — Schema.org pagination + pageStart/pageEnd; mirrored in BIBO
            if ref.get("pages"):
                pages = ref["pages"]
                g.add((article_uri, SDO.pagination, Literal(pages)))
                start, end = _split_pages(pages)
                if start:
                    g.add((article_uri, SDO.pageStart, Literal(start)))
                    g.add((article_uri, BIBO.pageStart, Literal(start)))
                if end:
                    g.add((article_uri, SDO.pageEnd, Literal(end)))
                    g.add((article_uri, BIBO.pageEnd, Literal(end)))

            # BIBO flat volume / issue (complement the Schema.org nested hierarchy below)
            if ref.get("volume"):
                g.add((article_uri, BIBO.volume, Literal(ref["volume"])))
            if ref.get("issue"):
                g.add((article_uri, BIBO.issue, Literal(ref["issue"])))

            # Schema.org journal hierarchy:
            #   ScholarlyArticle → isPartOf → PublicationIssue (if issue known)
            #                               → PublicationVolume (if volume known)
            #                               → Periodical
            if ref.get("journal"):
                journal = ref["journal"]
                journal_uri = ns[f"journal_{hash_string(journal)}"]
                g.add((journal_uri, RDF.type, SDO.Periodical))
                g.add((journal_uri, RDF.type, BIBO.Journal))
                g.add((journal_uri, SDO.name, Literal(journal)))

                if ref.get("volume"):
                    volume = ref["volume"]
                    volume_uri = ns[f"volume_{hash_string(journal + volume)}"]
                    g.add((volume_uri, RDF.type, SDO.PublicationVolume))
                    g.add((volume_uri, SDO.volumeNumber, Literal(volume)))
                    g.add((volume_uri, SDO.isPartOf, journal_uri))

                    if ref.get("issue"):
                        issue = ref["issue"]
                        issue_uri = ns[f"issue_{hash_string(journal + volume + issue)}"]
                        g.add((issue_uri, RDF.type, SDO.PublicationIssue))
                        g.add((issue_uri, SDO.issueNumber, Literal(issue)))
                        g.add((issue_uri, SDO.isPartOf, volume_uri))
                        g.add((article_uri, SDO.isPartOf, issue_uri))
                    else:
                        g.add((article_uri, SDO.isPartOf, volume_uri))
                else:
                    g.add((article_uri, SDO.isPartOf, journal_uri))

            # CiTO: Skeptical Science cites this article as evidence
            g.add((sks_uri, CITO.citesAsEvidence, article_uri))

            logging.info(f"Processed reference: {key}")

        except Exception as e:
            logging.error(f"Error processing reference '{key}': {e}")

    logging.info("References graph generation completed.")
    return g


def generate_citations_graph(
    articles_db: preserve.Connector,
    references_db: preserve.Connector,
) -> Graph:
    """Generate triples linking SkepticalScience ClaimReview articles to the scholarly references they cite.

    For each article in *articles_db* whose text mentions one or more reference
    keys, adds:

    * ``schema:citation <ClaimReview> → <ScholarlyArticle>``
    * ``cito:cites     <ClaimReview> → <ScholarlyArticle>``

    Article URIs follow the same ``claimreview_{hash}`` pattern used by
    :func:`climafactskg.builders.climafactskg.build_climafactskg`; reference
    URIs follow the ``article_{hash}`` pattern from
    :func:`generate_references_graph`.

    Args:
        articles_db: Preserve connector for the SkepticalScience arguments DB.
        references_db: Preserve connector for the references DB.

    Returns:
        Graph: RDFLib Graph containing the citation link triples.
    """
    from climafactskg.parsers.skepticalscience import SksMatcher

    # Build the tiptionary-shaped dict from stored DB records — no network call needed.
    logging.info("Building SksMatcher from references DB …")
    tiptionary = {
        ref["key"]: {
            "header": ref.get("header"),
            "matchType": ref.get("matchType"),
            "altKeys": ref.get("altKeys") or [],
        }
        for _, ref in references_db
        if ref.get("key")
    }
    logging.info("Index covers %d reference entries.", len(tiptionary))
    matcher = SksMatcher(tiptionary)

    ns = Namespace("https://purl.net/climatesense/climafactskg/ns#")
    g = Graph()

    citation_count = 0
    for _, article in articles_db:
        url = article.get("url") or article.get("main_url")
        if not url:
            continue

        # Concatenate the most informative text fields
        text = " ".join(
            filter(
                None,
                [
                    article.get("content"),
                    article.get("what_the_science_says"),
                    article.get("description"),
                ],
            )
        )
        if not text.strip():
            continue

        matched = matcher.get_matching_keys(text)
        if not matched:
            continue

        claimreview_uri = ns[f"claimreview_{hash_string(url)}"]
        for ref_key in matched:
            ref_uri = ns[f"article_{hash_string(ref_key.lower().strip())}"]
            g.add((claimreview_uri, SDO.citation, ref_uri))
            g.add((claimreview_uri, CITO.cites, ref_uri))
            citation_count += 1

    article_count = sum(1 for _ in g.subjects(SDO.citation, None))
    logging.info("Generated %d citation links across %d articles.", citation_count, article_count)
    return g


def build_references_graph(
    references_db: str = "data/skepticalscience_references_db.db",
) -> Graph:
    """Build and return the references RDF graph from a saved database.

    Args:
        references_db (str): Path to the SQLite database produced by
            ``process_skstiptionary``.

    Returns:
        Graph: The generated RDF graph.
    """
    with preserve.open(format="sqlite", filename=references_db) as db:
        return generate_references_graph(db)
