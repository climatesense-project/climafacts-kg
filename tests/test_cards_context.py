"""Tests for the deterministic review-context helpers (no network, no LLM)."""

import pytest
from climafactskg.classifiers.cards.context import select_context


class TestSelectContext:
    def test_never_cuts_mid_sentence(self):
        review = (
            "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima. "
            "Mike november oscar papa quebec romeo sierra tango uniform victor whiskey. "
            "Xray yankee zulu alpha bravo charlie delta echo foxtrot golf hotel india."
        )
        out = select_context(review, claim="unrelated", max_chars=150)
        assert out == (
            "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima. "
            "Mike november oscar papa quebec romeo sierra tango uniform victor whiskey."
        )

    def test_drops_claim_restatement_label_and_verdict(self):
        review = (
            "WHAT WAS CLAIMED The moon is made of cheese. OUR VERDICT False. "
            "Scientists have sampled lunar rock. It is basalt."
        )
        out = select_context(review, claim="The moon is made of cheese.")
        assert out == "Scientists have sampled lunar rock. It is basalt."

    def test_drops_paraphrased_restatement_but_keeps_new_information(self):
        review = "Volcanoes emit more CO2 than humans do, the post says. Human emissions are about 100 times larger."
        out = select_context(review, claim="Volcanoes emit more CO2 than humans do")
        assert out == "Human emissions are about 100 times larger."

    def test_strips_inline_verdict_but_keeps_surrounding_content(self):
        review = "Fact Check: The image is fabricated. Verdict: Mostly False The memo does not exist on the site."
        out = select_context(review, claim="q")
        assert "erdict" not in out
        assert "fabricated" in out and "memo does not exist" in out

    def test_oversized_first_sentence_is_cut_at_a_word_boundary_with_ellipsis(self):
        sentence = "Word " * 60 + "end."
        out = select_context(sentence, claim="unrelated", max_chars=100)
        assert out.endswith("…")
        assert len(out) <= 101
        body = out[:-1]
        assert sentence.startswith(body)
        assert sentence[len(body)] == " "  # cut landed on a word boundary

    def test_everything_dropped_returns_empty_string(self):
        assert select_context("OUR VERDICT False.", claim="x") == ""

    def test_no_budget_keeps_all_surviving_sentences(self):
        review = "First useful sentence here. Second useful sentence here."
        assert select_context(review, claim="zzz", max_chars=None) == review

    def test_abbreviations_do_not_split_sentences(self):
        review = "The U.S. emitted 5 Gt in 2020. Dr. Smith disagrees with the figure."
        assert select_context(review, claim="unrelated topic here", max_chars=800) == review
        assert select_context(review, claim="unrelated topic here", max_chars=45) == "The U.S. emitted 5 Gt in 2020."

    @pytest.mark.parametrize("review", ["", None, "   "])
    def test_empty_or_missing_review_returns_empty_string(self, review):
        assert select_context(review, claim="x") == ""

    def test_whitespace_is_collapsed(self):
        review = "Alpha   beta\tgamma delta.\n\nEpsilon zeta eta theta."
        assert select_context(review, claim="q") == "Alpha beta gamma delta. Epsilon zeta eta theta."

    def test_claim_with_regex_metacharacters_does_not_raise(self):
        claim = "A (test) [claim]? costs $5 a+b"
        review = f"WHAT WAS CLAIMED {claim} Independent analysts found the figures were wrong."
        assert select_context(review, claim=claim) == "Independent analysts found the figures were wrong."
