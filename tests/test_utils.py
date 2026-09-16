"""Regression tests for climafactskg.utils helpers."""

import io
from unittest.mock import MagicMock, patch

import pandas as pd
from climafactskg.utils import has_scientific_citation, query_sparqlendpoint


class TestQuerySparqlendpoint:
    @patch("climafactskg.utils.SPARQLWrapper")
    def test_empty_response_returns_empty_dataframe(self, mock_wrapper_cls):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT * WHERE {}")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_malformed_non_empty_response_returns_empty_dataframe(self, mock_wrapper_cls):
        # Inconsistent field counts across lines -> pandas.errors.ParserError, not EmptyDataError.
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"a,b,c\n1,2\n3,4,5,6\n")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT * WHERE {}")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_valid_csv_response_is_parsed(self, mock_wrapper_cls):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"s\nhttp://example.org/1\nhttp://example.org/2\n")
        mock_wrapper_cls.return_value = mock_wrapper

        df = query_sparqlendpoint("https://example.org/sparql", "SELECT ?s WHERE {}")

        assert list(df["s"]) == ["http://example.org/1", "http://example.org/2"]


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
