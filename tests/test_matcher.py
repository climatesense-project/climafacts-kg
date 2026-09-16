"""Tests for CARDSMatcher (rule-based Jaccard-similarity classifier).

Requires the spaCy model (`en_core_web_sm`) from the `matcher` extra.
"""

import pytest

spacy = pytest.importorskip("spacy")

from climafactskg.classifiers.cards.matcher import CARDSMatcher  # noqa: E402


class TestJaccardFromTokens:
    def test_identical_sets_score_one(self):
        tokens = frozenset({"ice", "melt"})
        assert CARDSMatcher._jaccard_from_tokens(tokens, tokens) == 1.0

    def test_disjoint_sets_score_zero(self):
        assert CARDSMatcher._jaccard_from_tokens({"ice"}, {"heat"}) == 0.0

    def test_partial_overlap(self):
        # intersection={"ice"} (1), union={"ice","melt","cold"} (3) -> 1/3
        score = CARDSMatcher._jaccard_from_tokens({"ice", "melt"}, {"ice", "cold"})
        assert score == pytest.approx(1 / 3)

    def test_both_empty_scores_zero(self):
        assert CARDSMatcher._jaccard_from_tokens(set(), set()) == 0.0


@pytest.fixture(scope="module")
def matcher():
    return CARDSMatcher()


class TestCARDSMatcherClassify:
    def test_unrelated_text_returns_default_code(self, matcher):
        assert matcher.classify("I like pizza and video games on weekends") == "0"

    def test_default_threshold_is_applied(self, matcher):
        # A near-empty/unrelated string should never clear the 0.25 default threshold.
        assert matcher.classify("") == "0"

    def test_taxonomy_is_default_taxonomy(self, matcher):
        from climafactskg.classifiers.cards.taxonomy import TAXONOMY

        assert matcher.taxonomy == TAXONOMY

    def test_classify_returns_a_valid_taxonomy_id_or_zero(self, matcher):
        result = matcher.classify("Ice isn't melting, glaciers are actually growing")
        ids = {entry["id"] for entry in matcher.taxonomy} | {"0"}
        assert result in ids

    def test_context_is_joined_into_the_text(self, matcher):
        # classify(text, context=ctx) must match classifying the manually joined string.
        text, ctx = "Sea levels are stable", "Ice isn't melting, glaciers are actually growing"
        assert matcher.classify(text, context=ctx) == matcher.classify(f"{text}\n\n{ctx}")

    def test_no_context_defaults_to_none(self, matcher):
        assert matcher.classify("I like pizza and video games on weekends", context=None) == "0"


class TestCARDSMatcherClassifyBatch:
    def test_batch_matches_sequential_classify(self, matcher):
        texts = ["I like pizza and video games", "Ice isn't melting, glaciers are actually growing"]
        assert matcher.classify_batch(texts) == [matcher.classify(t) for t in texts]

    def test_batch_applies_per_item_context(self, matcher):
        texts = ["", "irrelevant filler text"]
        contexts = ["Ice isn't melting, glaciers are actually growing", None]
        result = matcher.classify_batch(texts, contexts=contexts)
        expected = [matcher.classify(t, context=c) for t, c in zip(texts, contexts)]
        assert result == expected
