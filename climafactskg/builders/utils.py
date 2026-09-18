"""Shared helpers for builders/*.py graph construction."""

from rdflib import Graph, Namespace
from rdflib.namespace import NamespaceManager


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
