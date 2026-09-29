"""Tests that the ClimateSense dataset loaders attach and select review context from the sidecar."""

import logging

import pandas as pd
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
