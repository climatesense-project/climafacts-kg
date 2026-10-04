"""Shared helpers for builders/*.py graph construction."""

import re
import urllib.parse

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import NamespaceManager

from climafactskg.utils import strip_credential_query_params

# RFC 3986 characters that are safe to leave unencoded in a URI
_URI_SAFE = ":/?#[]@!$&'()*+,;=-._~%"

# XML 1.0 legal characters: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
_INVALID_XML_CHARS = re.compile(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]")


def normalize_text(value: str) -> str:
    """Collapse all whitespace runs (including newlines) to a single space and strip invalid XML characters.

    rdflib serialises any string containing newlines or double-quotes as a
    triple-quoted Turtle literal. Normalising here keeps every text Literal on one logical line
    and strips control characters (e.g. ASCII 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F) that break XML 1.0 serialization.
    """
    cleaned = _INVALID_XML_CHARS.sub("", value)
    return " ".join(cleaned.split())


def safe_uriref(url: str) -> URIRef:
    """Return a URIRef for *url*, percent-encoding any characters that are illegal in an IRI.

    Presigned-URL credentials (e.g. ``X-Amz-*``) are stripped first, so a URL stored before
    the parser learned to strip them can never reach the published graph.
    """
    return URIRef(urllib.parse.quote(strip_credential_query_params(url), safe=_URI_SAFE))


def new_graph(bindings: dict[str, Namespace]) -> Graph:
    """Return a new Graph with a fresh namespace manager bound to *bindings*.

    Every builder started a graph the same way — construct it, then replace
    its namespace manager with a fresh ``NamespaceManager`` and bind each
    prefix — repeated identically across builders/climafactskg.py,
    cimplekg.py, and sksreferenceskg.py. Note this does not exclude rdflib's
    built-in prefix table (rdf, rdfs, xsd, owl, ...) — those stay bound
    regardless; this only adds the given prefixes on top, matching the
    original per-builder behavior.

    Args:
        bindings: Prefix -> Namespace to bind, e.g. ``{"": ns, "cards": cards_ns}``.
            Use ``""`` for the default (unprefixed) namespace.

    Returns:
        A new, empty Graph with only the given prefixes bound.
    """
    g = Graph()
    g.namespace_manager = NamespaceManager(Graph())
    for prefix, ns in bindings.items():
        g.namespace_manager.bind(prefix, ns)
    return g
