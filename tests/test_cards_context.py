"""Tests for the deterministic review-context helpers (no network, no LLM)."""

import pandas as pd
import pytest
from climafactskg.classifiers.cards.context import (
    DEFAULT_CONTEXT_PATHS,
    build_climatesense_context,
    build_context_sidecar,
    fetch_cimplekg_reviews,
    load_input_reviews,
    select_context,
)


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


CIMPLE = "http://data.cimple.eu/claim-review/"


class TestLoadInputReviews:
    def test_maps_id_to_review_and_skips_blank_reviews(self, tmp_path):
        path = tmp_path / "inputs.csv"
        pd.DataFrame(
            {
                "id": ["https://a.example/1", "https://a.example/2", "https://a.example/3"],
                "data_source": ["x", "x", "x"],
                "claim_type": ["claim", "claim", "claim"],
                "claim": ["c1", "c2", "c3"],
                "review": ["Review one.", "", None],
            }
        ).to_csv(path, index=False)

        assert load_input_reviews(str(path)) == {"https://a.example/1": "Review one."}


class TestFetchCimpleKGReviews:
    def test_chunks_dedupes_and_returns_only_found_texts(self):
        calls = []

        def query_fn(endpoint, query):
            calls.append((endpoint, query))
            found = [(u, f"text for {u}") for u in (f"{CIMPLE}a", f"{CIMPLE}c") if f"<{u}>" in query]
            return pd.DataFrame(found, columns=["rev", "text"]) if found else pd.DataFrame()

        uris = [f"{CIMPLE}a", f"{CIMPLE}b", f"{CIMPLE}c", f"{CIMPLE}d", f"{CIMPLE}a"]
        result = fetch_cimplekg_reviews(uris, chunk_size=2, query_fn=query_fn, endpoint="http://endpoint.test")

        assert result == {f"{CIMPLE}a": f"text for {CIMPLE}a", f"{CIMPLE}c": f"text for {CIMPLE}c"}
        assert len(calls) == 2  # 4 unique uris / chunk_size 2
        assert all(endpoint == "http://endpoint.test" for endpoint, _ in calls)
        assert f"<{CIMPLE}a>" in calls[0][1] and f"<{CIMPLE}b>" in calls[0][1]

    def test_ignores_blank_and_non_string_texts(self):
        def query_fn(endpoint, query):
            return pd.DataFrame({"rev": [f"{CIMPLE}a", f"{CIMPLE}b"], "text": ["   ", None]})

        assert fetch_cimplekg_reviews([f"{CIMPLE}a", f"{CIMPLE}b"], query_fn=query_fn) == {}


class TestBuildContextSidecar:
    def test_local_inputs_win_and_only_cimplekg_ids_are_fetched(self, tmp_path):
        inputs = tmp_path / "inputs.csv"
        pd.DataFrame({"id": [f"{CIMPLE}local"], "review": ["Local review."]}).to_csv(inputs, index=False)
        fetched_with = []

        def fetch_fn(uris):
            fetched_with.append(list(uris))
            return {f"{CIMPLE}remote": "Remote review."}

        ids = [f"{CIMPLE}local", f"{CIMPLE}remote", f"{CIMPLE}missing", "https://skepticalscience.com/skeptic_X.htm"]
        df = build_context_sidecar(ids, input_csvs=[str(inputs)], fetch_fn=fetch_fn)

        assert fetched_with == [[f"{CIMPLE}remote", f"{CIMPLE}missing"]]  # local id and non-CimpleKG id not fetched
        assert list(df.columns) == ["document_id", "context_source", "context"]
        by_id = df.set_index("document_id")
        assert by_id.loc[f"{CIMPLE}local", "context_source"] == "input_csv"
        assert by_id.loc[f"{CIMPLE}remote", "context_source"] == "cimplekg"
        assert f"{CIMPLE}missing" not in by_id.index
        assert "https://skepticalscience.com/skeptic_X.htm" not in by_id.index

    def test_malformed_ids_are_never_fetched(self):
        fetched_with = []

        def fetch_fn(uris):
            fetched_with.append(list(uris))
            return {}

        bad = [f"{CIMPLE}has space", f"{CIMPLE}a>b", f"{CIMPLE}x<y", f"{CIMPLE}ok"]
        build_context_sidecar(bad, fetch_fn=fetch_fn)

        assert fetched_with == [[f"{CIMPLE}ok"]]

    def test_no_fetch_when_nothing_is_eligible(self):
        def fetch_fn(uris):
            raise AssertionError("fetch_fn must not be called")

        df = build_context_sidecar(["https://example.org/quote"], fetch_fn=fetch_fn)

        assert df.empty
        assert list(df.columns) == ["document_id", "context_source", "context"]


class TestBuildClimatesenseContext:
    def _consensus(self, tmp_path, ids):
        path = tmp_path / "consensus.csv"
        pd.DataFrame({"document_id": ids, "content": ["c"] * len(ids), "cards_code": ["1_1"] * len(ids)}).to_csv(
            path, index=False
        )
        return str(path)

    def test_writes_sidecar_then_reuses_it_unless_forced(self, tmp_path):
        consensus = self._consensus(tmp_path, [f"{CIMPLE}a"])
        sidecar = str(tmp_path / "context.csv")
        calls = []

        def fetch_fn(uris):
            calls.append(list(uris))
            return {f"{CIMPLE}a": f"Review {len(calls)}."}

        first = build_climatesense_context("v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn)
        again = build_climatesense_context("v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn)
        forced = build_climatesense_context(
            "v1", consensus_path=consensus, context_path=sidecar, fetch_fn=fetch_fn, force=True
        )

        assert first.loc[0, "context"] == "Review 1."
        assert again.loc[0, "context"] == "Review 1."  # cached file reused, no second fetch
        assert forced.loc[0, "context"] == "Review 2."
        assert len(calls) == 2
        assert pd.read_csv(sidecar).loc[0, "context"] == "Review 2."
        assert not (tmp_path / "context.csv.tmp").exists()

    def test_failed_fetch_leaves_no_sidecar(self, tmp_path):
        consensus = self._consensus(tmp_path, [f"{CIMPLE}a"])
        sidecar = tmp_path / "context.csv"

        def fetch_fn(uris):
            raise RuntimeError("endpoint down")

        with pytest.raises(RuntimeError, match="endpoint down"):
            build_climatesense_context("v1", consensus_path=consensus, context_path=str(sidecar), fetch_fn=fetch_fn)

        assert not sidecar.exists()

    def test_missing_consensus_csv_raises_a_helpful_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="consensus"):
            build_climatesense_context(
                "v1", consensus_path=str(tmp_path / "nope.csv"), context_path=str(tmp_path / "c.csv")
            )

    def test_default_paths_sit_next_to_the_consensus_csvs(self):
        assert DEFAULT_CONTEXT_PATHS["v1"] == "data/cards_annotations_v2/cards_annotations_context.csv"
        assert DEFAULT_CONTEXT_PATHS["v2"] == "data/cards_annotations_v2b/cards_annotations_context.csv"
