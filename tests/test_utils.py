"""Regression tests for climafactskg.utils helpers."""

import io
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
from climafactskg.utils import has_scientific_citation, query_sparqlendpoint


class TestQuerySparqlendpoint:
    # query_sparqlendpoint is wrapped in lru_cache, keyed on every argument
    # including cache_dir — each test passes its own tmp_path so tests can't
    # collide on cache entries with each other (several use the same
    # endpoint_url + query on purpose, to exercise different response bodies).

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_empty_response_returns_empty_dataframe(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT * WHERE {}", cache_dir=str(tmp_path))

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_malformed_non_empty_response_returns_empty_dataframe(self, mock_wrapper_cls, tmp_path):
        # Inconsistent field counts across lines -> pandas.errors.ParserError, not EmptyDataError.
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"a,b,c\n1,2\n3,4,5,6\n")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT * WHERE {}", cache_dir=str(tmp_path))

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_valid_csv_response_is_parsed(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"s\nhttp://example.org/1\nhttp://example.org/2\n")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT ?s WHERE {}", cache_dir=str(tmp_path))

        assert list(df["s"]) == ["http://example.org/1", "http://example.org/2"]

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_second_call_uses_disk_cache_not_a_new_request(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"s\nhttp://example.org/1\n")
        mock_wrapper_cls.return_value = mock_wrapper

        query_sparqlendpoint.cache_clear()
        query_sparqlendpoint("https://example.org/sparql", "SELECT ?s WHERE {} #1", cache_dir=str(tmp_path))
        query_sparqlendpoint.cache_clear()  # drop the in-memory layer; disk cache must still be hit
        df2 = query_sparqlendpoint("https://example.org/sparql", "SELECT ?s WHERE {} #1", cache_dir=str(tmp_path))

        assert mock_wrapper_cls.call_count == 1
        assert list(df2["s"]) == ["http://example.org/1"]

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_expired_cache_triggers_a_new_request(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"s\nhttp://example.org/1\n")
        mock_wrapper_cls.return_value = mock_wrapper

        query_sparqlendpoint.cache_clear()
        query_sparqlendpoint(
            "https://example.org/sparql",
            "SELECT ?s WHERE {} #2",
            cache_dir=str(tmp_path),
            cache_expiry=timedelta(seconds=-1),  # already expired
        )
        query_sparqlendpoint.cache_clear()
        query_sparqlendpoint(
            "https://example.org/sparql",
            "SELECT ?s WHERE {} #2",
            cache_dir=str(tmp_path),
            cache_expiry=timedelta(seconds=-1),
        )

        assert mock_wrapper_cls.call_count == 2


class TestHasScientificCitation:
    def test_apa_parenthetical(self):
        assert has_scientific_citation("Global temperatures are rising (IPCC, 2021).")

    def test_narrative_et_al(self):
        assert has_scientific_citation("Hansen et al. (2010) found evidence of warming.")

    def test_numbered_reference(self):
        assert has_scientific_citation("This has been shown previously [1, 2].")

    def test_doi(self):
        assert has_scientific_citation("See doi:10.1038/nature12345 for details.")

    def test_no_citation(self):
        assert not has_scientific_citation("The weather was nice today.")
