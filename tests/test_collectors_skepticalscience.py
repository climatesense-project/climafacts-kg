"""One URL that cannot be fetched must not block the rest; the step still reports the failure at the end."""

from unittest.mock import patch

import pytest
import requests
from climafactskg.collectors import skepticalscience as sks

URLS = ["https://sks.test/a", "https://sks.test/bad", "https://sks.test/c"]


def _fetch(url):
    if url.endswith("/bad"):
        raise ValueError(f"Failed to fetch URL content for '{url}'. Status code: 500")
    return f"<html>{url}</html>"


class TestProcessMisinformersUrls:
    def test_the_other_urls_are_still_stored_and_the_failure_is_raised_at_the_end(self):
        db: dict = {}
        with (
            patch.object(sks, "fetch_url_content", side_effect=_fetch),
            patch.object(sks, "parse_misinformer_article", side_effect=lambda url, content: {"url": url}),
        ):
            with pytest.raises(RuntimeError, match="1 of 3.*sks.test/bad"):
                sks.process_misinformers_urls(db, URLS)

        assert sorted(db) == ["https://sks.test/a", "https://sks.test/c"]  # the bad URL did not block the third

    def test_a_connection_error_is_handled_the_same_way(self):
        db: dict = {}
        with (
            patch.object(sks, "fetch_url_content", side_effect=requests.ConnectionError("down")),
            patch.object(sks, "parse_misinformer_article"),
        ):
            with pytest.raises(RuntimeError, match="3 of 3"):
                sks.process_misinformers_urls(db, URLS)

    def test_no_failure_means_no_error(self):
        db: dict = {}
        with (
            patch.object(sks, "fetch_url_content", return_value="<html></html>"),
            patch.object(sks, "parse_misinformer_article", side_effect=lambda url, content: {"url": url}),
        ):
            sks.process_misinformers_urls(db, URLS)

        assert len(db) == 3


class TestProcessUrls:
    def test_the_other_urls_are_still_stored_and_the_failure_is_raised_at_the_end(self):
        db: dict = {}

        def parse(url, html=None):
            if url.endswith("/bad"):
                raise ValueError(f"Failed to fetch URL content for '{url}'. Status code: 500")
            return {"url": url, "lang": "en"}

        with (
            patch.object(sks, "fetch_url_content", side_effect=_fetch),
            patch.object(sks, "parse_main_article", side_effect=lambda url, content=None: parse(url)),
        ):
            with pytest.raises(RuntimeError, match="1 of 3.*sks.test/bad"):
                sks.process_urls(db, URLS)

        assert sorted(db) == ["https://sks.test/a", "https://sks.test/c"]
