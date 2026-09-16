"""Tests for builders/climafactskg.py's cards_category exclusion logic.

Regression coverage for a bug where the "0" not-related sentinel (used by the
transformer/matcher engines) was not excluded, only "0_0" (the LLM engine's
sentinel) — see builders/cimplekg.py's equivalent, correct check for comparison.
"""

import preserve
from climafactskg.builders.climafactskg import generate_climafactskg_base
from rdflib import SDO, Namespace

CARDS_NS = Namespace("https://purl.net/climatesense/cards/ns#")


def _make_entry(url: str, cards_category=None) -> dict:
    return {
        "url": url,
        "lang": "en",
        "main_url": url,
        "languages": [],
        "climate_myth": "Some myth text",
        "title": "Some title",
        "what_the_science_says": "Some rebuttal",
        "cards_category": cards_category,
    }


def _build_graph(tmp_path, entry):
    db_path = str(tmp_path / "arguments.db")
    with preserve.open(format="sqlite", filename=db_path) as db:
        db[entry["url"]] = entry
    with preserve.open(format="sqlite", filename=db_path) as db:
        return generate_climafactskg_base(db)


class TestCardsCategoryExclusion:
    def test_transformer_not_related_sentinel_adds_no_about_link(self, tmp_path):
        g = _build_graph(tmp_path, _make_entry("http://example.org/a", cards_category="0"))
        assert not list(g.triples((None, SDO.about, None)))

    def test_llm_not_related_sentinel_adds_no_about_link(self, tmp_path):
        g = _build_graph(tmp_path, _make_entry("http://example.org/b", cards_category="0_0"))
        assert not list(g.triples((None, SDO.about, None)))

    def test_real_category_adds_about_link(self, tmp_path):
        g = _build_graph(tmp_path, _make_entry("http://example.org/c", cards_category="1_1"))
        about_triples = list(g.triples((None, SDO.about, None)))
        assert len(about_triples) == 1
        assert about_triples[0][2] == CARDS_NS["1_1"]

    def test_missing_category_adds_no_about_link(self, tmp_path):
        g = _build_graph(tmp_path, _make_entry("http://example.org/d", cards_category=None))
        assert not list(g.triples((None, SDO.about, None)))
