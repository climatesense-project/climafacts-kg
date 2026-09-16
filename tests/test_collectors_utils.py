"""Tests for the shared claim-review collector pipeline in collectors/utils.py.

CimpleKG and ClimateSenseKG both delegate their process_claims/classify_claims/
process_all to process_claim_reviews/classify_claim_reviews/process_all_claim_reviews
here — this is the declared contract a new SPARQL ClaimReview source can reuse,
replacing the old setup where climatesensekg.py silently imported cimplekg.py's
functions directly and only worked by coincidental column-name match.
"""

import pandas as pd
import preserve
from climafactskg.collectors.utils import process_claim_reviews


def _make_db(tmp_path):
    return preserve.open(format="sqlite", filename=str(tmp_path / "test.db"))


class TestProcessClaimReviews:
    def test_stores_new_claim_with_detected_language(self, tmp_path):
        df = pd.DataFrame(
            [{"rev": "http://example.org/claim/1", "date_published": "2026-01-01", "text": "The sky is blue."}]
        )
        with _make_db(tmp_path) as db:
            process_claim_reviews(db, df)
            entry = db["http://example.org/claim/1"]

        assert entry["url"] == "http://example.org/claim/1"
        assert entry["date_published"] == "2026-01-01"
        assert entry["claim"] == "The sky is blue."
        assert entry["lang"] == "en"

    def test_skips_already_stored_url(self, tmp_path):
        df = pd.DataFrame([{"rev": "http://example.org/claim/2", "date_published": "2026-01-01", "text": "Text."}])
        with _make_db(tmp_path) as db:
            db["http://example.org/claim/2"] = {"url": "http://example.org/claim/2", "claim": "already here"}
            process_claim_reviews(db, df)
            entry = db["http://example.org/claim/2"]

        # Untouched — the existing entry is not overwritten by re-processing.
        assert entry["claim"] == "already here"

    def test_skips_rows_with_no_text(self, tmp_path):
        df = pd.DataFrame([{"rev": "http://example.org/claim/3", "date_published": "2026-01-01", "text": None}])
        with _make_db(tmp_path) as db:
            process_claim_reviews(db, df)
            assert "http://example.org/claim/3" not in db

    def test_two_sources_produce_identical_entry_shape(self, tmp_path):
        # The whole point of the shared function: any source whose fetch_claims()
        # DataFrame has these three columns gets the exact same stored shape,
        # regardless of which collector module called in.
        cimplekg_df = pd.DataFrame(
            [{"rev": "http://data.cimple.eu/claim/1", "date_published": "2026-01-01", "text": "Claim A"}]
        )
        climatesense_df = pd.DataFrame(
            [{"rev": "http://data.climatesense-project.eu/claim/1", "date_published": "2026-01-01", "text": "Claim B"}]
        )
        with _make_db(tmp_path) as db:
            process_claim_reviews(db, cimplekg_df)
            process_claim_reviews(db, climatesense_df)
            a = db["http://data.cimple.eu/claim/1"]
            b = db["http://data.climatesense-project.eu/claim/1"]

        assert set(a.keys()) == set(b.keys()) == {"url", "date_published", "claim", "lang"}
