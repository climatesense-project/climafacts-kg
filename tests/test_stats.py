"""Tests for climafactskg.stats.count_graph_stats.

This is the RDF validity/sanity check backing the `climafactskg validate` CLI command.
"""

import pytest
from climafactskg.stats import count_graph_stats

_VALID_TTL = """
@prefix sc: <https://schema.org/> .
@prefix cito: <http://purl.org/spar/cito/> .

<http://example.org/review1> a sc:ClaimReview ;
    sc:citation <http://example.org/article1> .

<http://example.org/article1> a sc:ScholarlyArticle ;
    cito:cites <http://example.org/article2> .
"""

_EMPTY_TTL = ""

_MALFORMED_TTL = "this is not valid turtle {{{ @broken"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return str(path)


class TestCountGraphStats:
    def test_valid_graph_counts_correctly(self, tmp_path):
        path = _write(tmp_path, "valid.ttl", _VALID_TTL)
        stats = count_graph_stats(path)
        assert stats["total_triples"] == 4
        assert stats["claim_reviews"] == 1
        assert stats["scholarly_articles"] == 1
        assert stats["sc_citations"] == 1
        assert stats["cito_cites"] == 1

    def test_empty_graph_has_zero_triples(self, tmp_path):
        path = _write(tmp_path, "empty.ttl", _EMPTY_TTL)
        stats = count_graph_stats(path)
        assert stats["total_triples"] == 0
        assert stats["claim_reviews"] == 0

    def test_malformed_turtle_raises(self, tmp_path):
        # rdflib's Turtle/N3 parser raises SyntaxError (specifically BadSyntax)
        # on malformed input — this is exactly what `climafactskg validate`
        # catches to report a broken build.
        path = _write(tmp_path, "bad.ttl", _MALFORMED_TTL)
        with pytest.raises(SyntaxError):
            count_graph_stats(path)
