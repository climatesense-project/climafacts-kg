"""Tests that the ClimateSense dataset loaders attach and select review context from the sidecar."""

import logging

import pandas as pd
import pytest
from climafactskg.classifiers.cards import datasets
from climafactskg.classifiers.cards.datasets import _attach_context, climatesense_dataset_v1

CIMPLE = "http://data.cimple.eu/claim-review/"


def _write_consensus(tmp_path, rows):
    path = tmp_path / "consensus.csv"
    pd.DataFrame(
        [
            {
                "document_id": doc_id,
                "content": content,
                "source": "CimpleKG",
                "type": "claim",
                "cards_code": "1_1",
                "agreement_info": "{}",
            }
            for doc_id, content in rows
        ]
    ).to_csv(path, index=False)
    return str(path)


def _write_sidecar(tmp_path, rows):
    path = tmp_path / "context.csv"
    pd.DataFrame(rows, columns=["document_id", "context_source", "context"]).to_csv(path, index=False)
    return str(path)


def _contexts(dataset):
    return {case.name: case.inputs.context for case in dataset.cases}


class TestLoaderContext:
    def test_attaches_selected_context_and_leaves_others_none(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "The moon is cheese."), (f"{CIMPLE}b", "Other claim.")])
        sidecar = _write_sidecar(
            tmp_path,
            [
                (
                    f"{CIMPLE}a",
                    "cimplekg",
                    "WHAT WAS CLAIMED The moon is cheese. OUR VERDICT False. "
                    "Scientists sampled the lunar rock and found basalt.",
                )
            ],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds) == {
            f"{CIMPLE}a": "Scientists sampled the lunar rock and found basalt.",
            f"{CIMPLE}b": None,
        }

    def test_missing_sidecar_still_loads_with_a_warning(self, tmp_path, caplog):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])

        with caplog.at_level(logging.WARNING):
            ds = climatesense_dataset_v1(path=consensus, context_path=str(tmp_path / "absent.csv"))

        assert _contexts(ds) == {f"{CIMPLE}a": None}
        assert any("context" in record.message.lower() for record in caplog.records)

    def test_context_path_none_disables_context_without_warning(self, tmp_path, caplog):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])

        with caplog.at_level(logging.WARNING):
            ds = climatesense_dataset_v1(path=consensus, context_path=None)

        assert _contexts(ds) == {f"{CIMPLE}a": None}
        assert not caplog.records

    def test_duplicate_sidecar_rows_do_not_duplicate_cases(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        sidecar = _write_sidecar(
            tmp_path,
            [
                (f"{CIMPLE}a", "input_csv", "First independent finding here."),
                (f"{CIMPLE}a", "cimplekg", "Second independent finding here."),
            ],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert len(ds.cases) == 1
        assert _contexts(ds)[f"{CIMPLE}a"] == "First independent finding here."

    def test_blank_and_boilerplate_only_reviews_become_none(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a."), (f"{CIMPLE}b", "Claim b.")])
        sidecar = _write_sidecar(
            tmp_path,
            [(f"{CIMPLE}a", "cimplekg", ""), (f"{CIMPLE}b", "cimplekg", "OUR VERDICT False.")],
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds) == {f"{CIMPLE}a": None, f"{CIMPLE}b": None}

    def test_max_context_chars_is_applied(self, tmp_path):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        review = " ".join(f"Sentence number {i} says something entirely new and different." for i in range(30))
        sidecar = _write_sidecar(tmp_path, [(f"{CIMPLE}a", "cimplekg", review)])

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar, max_context_chars=200)

        context = _contexts(ds)[f"{CIMPLE}a"]
        assert 0 < len(context) <= 200
        assert context.endswith(".")  # whole sentences only

    def test_claim_with_regex_metacharacters_loads(self, tmp_path):
        claim = "A (test) [claim]? costs $5 a+b"
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", claim)])
        sidecar = _write_sidecar(
            tmp_path, [(f"{CIMPLE}a", "cimplekg", f"{claim} Independent analysts found the figures were wrong.")]
        )

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert _contexts(ds)[f"{CIMPLE}a"] == "Independent analysts found the figures were wrong."


def test_nan_claim_does_not_corrupt_the_review(tmp_path):
    df = pd.DataFrame({"document_id": ["d1"], "content": [float("nan")]})
    sidecar = _write_sidecar(tmp_path, [("d1", "cimplekg", "The financial analysts found the figures were wrong.")])

    out = _attach_context(df, sidecar, 800)

    assert (
        out.loc[0, "context"] == "The financial analysts found the figures were wrong."
    )  # "nan" in "financial" intact


class TestContextIsOptIn:
    def test_plain_factory_call_stays_claim_only_even_when_a_sidecar_exists(self, tmp_path, monkeypatch):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        sidecar = _write_sidecar(tmp_path, [(f"{CIMPLE}a", "cimplekg", "An independent finding about this claim.")])
        monkeypatch.setitem(datasets.DEFAULT_CONTEXT_PATHS, "v1", sidecar)

        assert _contexts(climatesense_dataset_v1(path=consensus)) == {f"{CIMPLE}a": None}

    def test_with_context_uses_the_default_sidecar(self, tmp_path, monkeypatch):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        sidecar = _write_sidecar(tmp_path, [(f"{CIMPLE}a", "cimplekg", "An independent finding about this claim.")])
        monkeypatch.setitem(datasets.DEFAULT_CONTEXT_PATHS, "v1", sidecar)

        ds = climatesense_dataset_v1(path=consensus, with_context=True)

        assert _contexts(ds) == {f"{CIMPLE}a": "An independent finding about this claim."}

    def test_an_explicit_context_path_also_opts_in_and_wins_over_the_default(self, tmp_path, monkeypatch):
        consensus = _write_consensus(tmp_path, [(f"{CIMPLE}a", "Claim a.")])
        default_sidecar = _write_sidecar(tmp_path, [(f"{CIMPLE}a", "cimplekg", "The default sidecar finding is here.")])
        monkeypatch.setitem(datasets.DEFAULT_CONTEXT_PATHS, "v1", default_sidecar)
        other = tmp_path / "other.csv"
        pd.DataFrame(
            [(f"{CIMPLE}a", "cimplekg", "The explicit sidecar finding is here.")],
            columns=["document_id", "context_source", "context"],
        ).to_csv(other, index=False)

        ds = climatesense_dataset_v1(path=consensus, context_path=str(other), with_context=True)

        assert _contexts(ds) == {f"{CIMPLE}a": "The explicit sidecar finding is here."}


class TestOnlyWithContext:
    def _setup(self, tmp_path):
        consensus = _write_consensus(
            tmp_path, [(f"{CIMPLE}a", "Claim a."), (f"{CIMPLE}b", "Claim b."), (f"{CIMPLE}c", "Claim c.")]
        )
        sidecar = _write_sidecar(
            tmp_path,
            [
                (f"{CIMPLE}b", "cimplekg", "An independent finding about claim b."),
                (f"{CIMPLE}c", "cimplekg", "An independent finding about claim c."),
            ],
        )
        return consensus, sidecar

    def test_keeps_only_cases_that_have_context(self, tmp_path):
        consensus, sidecar = self._setup(tmp_path)

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar, only_with_context=True)

        assert sorted(_contexts(ds)) == [f"{CIMPLE}b", f"{CIMPLE}c"]

    def test_limit_applies_after_the_context_filter(self, tmp_path):
        consensus, sidecar = self._setup(tmp_path)

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar, only_with_context=True, limit=1)

        assert list(_contexts(ds)) == [f"{CIMPLE}b"]  # the first case overall has no context and is not counted

    def test_default_keeps_every_case(self, tmp_path):
        consensus, sidecar = self._setup(tmp_path)

        ds = climatesense_dataset_v1(path=consensus, context_path=sidecar)

        assert len(ds.cases) == 3

    def test_requires_context_to_be_enabled(self, tmp_path):
        consensus, _ = self._setup(tmp_path)

        with pytest.raises(ValueError, match="only_with_context"):
            climatesense_dataset_v1(path=consensus, only_with_context=True)
