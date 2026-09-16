"""Tests for builders/cimplekg.py's shared add_cards_category_link helper.

Used by both builders/cimplekg.py (CimpleKG/ClimateSenseKG mappings) and
builders/climafactskg.py (SkS arguments) so the not-related sentinel
exclusion can't drift between them again.
"""

from climafactskg.builders.cimplekg import add_cards_category_link
from rdflib import SDO, Graph, Namespace, URIRef

CARDS_NS = Namespace("https://purl.net/climatesense/cards/ns#")
SUBJECT = URIRef("http://example.org/a")


class TestAddCardsCategoryLink:
    def test_real_category_adds_link_and_returns_true(self):
        g = Graph()
        added = add_cards_category_link(g, CARDS_NS, SUBJECT, "1_1")
        assert added is True
        assert (SUBJECT, SDO.about, CARDS_NS["1_1"]) in g
        assert (CARDS_NS["1_1"], SDO.subjectOf, SUBJECT) in g

    def test_transformer_sentinel_adds_nothing(self):
        g = Graph()
        added = add_cards_category_link(g, CARDS_NS, SUBJECT, "0")
        assert added is False
        assert len(g) == 0

    def test_llm_sentinel_adds_nothing(self):
        g = Graph()
        added = add_cards_category_link(g, CARDS_NS, SUBJECT, "0_0")
        assert added is False
        assert len(g) == 0

    def test_none_adds_nothing(self):
        g = Graph()
        added = add_cards_category_link(g, CARDS_NS, SUBJECT, None)
        assert added is False
        assert len(g) == 0
