"""Regression tests for climafactskg.utils helpers."""

import io
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
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
    def test_timeout_is_passed_to_the_wrapper(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"a,b\n1,2\n")
        mock_wrapper_cls.return_value = mock_wrapper

        query_sparqlendpoint("https://example.org/sparql", "SELECT 1", cache_dir=str(tmp_path), timeout=5)

        mock_wrapper.setTimeout.assert_called_once_with(5)

    @patch("climafactskg.utils.SPARQLWrapper")
    def test_no_timeout_leaves_the_wrapper_default(self, mock_wrapper_cls, tmp_path):
        mock_wrapper = MagicMock()
        mock_wrapper.query.return_value.response = io.BytesIO(b"a,b\n1,2\n")
        mock_wrapper_cls.return_value = mock_wrapper

        query_sparqlendpoint("https://example.org/sparql", "SELECT 2", cache_dir=str(tmp_path))

        mock_wrapper.setTimeout.assert_not_called()

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


class TestFetchUrlContent:
    def _response(self, status=200, text="<html>page</html>"):
        response = MagicMock()
        response.status_code = status
        response.ok = status < 400
        response.text = text
        return response

    def test_a_successful_page_is_returned_and_cached(self, tmp_path):
        from climafactskg.utils import fetch_url_content

        with patch("climafactskg.utils.requests.get", return_value=self._response()) as get:
            first = fetch_url_content("https://x.test/a", cache_dir=str(tmp_path))
            second = fetch_url_content("https://x.test/a", cache_dir=str(tmp_path))

        assert first == second == "<html>page</html>"
        assert get.call_count == 1  # the second call came from the cache

    def test_requests_carry_a_timeout(self, tmp_path):
        from climafactskg.utils import fetch_url_content

        with patch("climafactskg.utils.requests.get", return_value=self._response()) as get:
            fetch_url_content("https://x.test/a", cache_dir=str(tmp_path))

        assert get.call_args.kwargs["timeout"] > 0  # a hung server must not stall the collector forever

    @pytest.mark.parametrize("status", [404, 429, 500, 503])
    def test_an_error_status_raises_and_is_not_cached(self, tmp_path, status):
        from climafactskg.utils import fetch_url_content

        with patch("climafactskg.utils.requests.get", return_value=self._response(status, "<html>oops</html>")):
            with pytest.raises(ValueError, match=str(status)):
                fetch_url_content("https://x.test/a", cache_dir=str(tmp_path))
        with patch("climafactskg.utils.requests.get", return_value=self._response()) as get:
            assert fetch_url_content("https://x.test/a", cache_dir=str(tmp_path)) == "<html>page</html>"
        assert get.call_count == 1  # the failed response was not served from the cache

    def test_no_partial_cache_file_is_left_behind(self, tmp_path):
        from climafactskg.utils import fetch_url_content

        with patch("climafactskg.utils.requests.get", return_value=self._response()):
            fetch_url_content("https://x.test/a", cache_dir=str(tmp_path))

        assert not list(tmp_path.glob("*.tmp"))
