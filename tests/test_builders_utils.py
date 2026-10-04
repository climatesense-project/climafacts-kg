"""Tests for builders/utils.py's shared new_graph helper."""

from climafactskg.builders.utils import new_graph, normalize_text, safe_uriref
from rdflib import Namespace

NS = Namespace("http://example.org/ns#")
OTHER_NS = Namespace("http://example.org/other#")


class TestNormalizeText:
    def test_collapses_whitespace(self):
        assert normalize_text("  hello \n \t world  ") == "hello world"

    def test_strips_invalid_xml_control_characters(self):
        # \x03 (ETX), \x00 (NUL), \x08 (BS), \x1F (US) are illegal in XML 1.0
        text = "latitude of 80\x03.\x00\x08\x1f Even allowing for..."
        assert normalize_text(text) == "latitude of 80. Even allowing for..."

    def test_preserves_valid_unicode(self):
        text = "Temperature in °C — 80° latitude."
        assert normalize_text(text) == "Temperature in °C — 80° latitude."


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


class TestSafeUriref:
    def test_strips_presigned_credentials(self):
        url = (
            "https://s3.amazonaws.com/bucket/paper.pdf?response-content-disposition=inline"
            "&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIAEXAMPLE%2F20200406%2Fus-east-1%2Fs3%2Faws4_request"
            "&X-Amz-Security-Token=secret&X-Amz-Signature=abc123"
        )
        result = str(safe_uriref(url))
        assert result.startswith("https://s3.amazonaws.com/bucket/paper.pdf?response-content-disposition=inline")
        assert "X-Amz" not in result and "secret" not in result

    def test_leaves_ordinary_urls_untouched(self):
        url = "https://example.org/a%20b?q=1,2&tag=x:y"
        assert str(safe_uriref(url)) == url
