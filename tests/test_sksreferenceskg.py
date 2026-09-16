"""Regression tests for climafactskg.builders.sksreferenceskg's private helpers."""

from climafactskg.builders.sksreferenceskg import _canonical_doi, _split_authors, _split_pages, _split_sentences


class TestSplitSentences:
    def test_short_citation_fragment_is_kept(self):
        # Previously dropped by a "len(s.strip()) > 20" filter, silently losing
        # short standalone citations before they ever reached the matcher.
        sentences = _split_sentences("(Foster, 2010). Global warming continues.")
        assert "(Foster, 2010)." in sentences

    def test_splits_on_sentence_boundaries(self):
        sentences = _split_sentences("First sentence. Second sentence.")
        assert sentences == ["First sentence.", "Second sentence."]

    def test_empty_fragments_are_dropped(self):
        assert "" not in _split_sentences("First.  Second.")

    def test_single_short_sentence_document_is_not_empty(self):
        # A whole-document text that is itself short must still be matched,
        # not silently reduced to an empty sentence list.
        assert _split_sentences("See IPCC AR6.") == ["See IPCC AR6."]


class TestSplitAuthors:
    def test_splits_ampersand_pair(self):
        assert _split_authors("Smith, J. & Jones, K.") == ["Smith, J.", "Jones, K."]

    def test_single_author(self):
        assert _split_authors("Smith, J.") == ["Smith, J."]


class TestCanonicalDoi:
    def test_bare_doi(self):
        result = _canonical_doi("10.1038/nature12345")
        assert result is not None
        assert "10.1038/nature12345" in result[0]

    def test_doi_url(self):
        result = _canonical_doi("https://doi.org/10.1038/nature12345")
        assert result is not None


class TestSplitPages:
    def test_hyphen_range(self):
        assert _split_pages("3466-3468") == ("3466", "3468")

    def test_en_dash_range(self):
        assert _split_pages("3466–3468") == ("3466", "3468")
