"""Tests for builders/utils.py's shared new_graph helper."""

from climafactskg.builders.utils import new_graph
from rdflib import Namespace

NS = Namespace("http://example.org/ns#")
OTHER_NS = Namespace("http://example.org/other#")


class TestNewGraph:
    def test_binds_given_prefixes(self):
        g = new_graph({"ex": NS, "other": OTHER_NS})
        namespaces = {prefix: str(uri) for prefix, uri in g.namespace_manager.namespaces()}
        assert namespaces["ex"] == str(NS)
        assert namespaces["other"] == str(OTHER_NS)

    def test_default_prefix_supported(self):
        g = new_graph({"": NS})
        namespaces = {prefix: str(uri) for prefix, uri in g.namespace_manager.namespaces()}
        assert namespaces[""] == str(NS)

    def test_graph_starts_empty(self):
        g = new_graph({"ex": NS})
        assert len(g) == 0
