"""Tests for the LLM options of climafactskg.cli's `process` command.

`process --classifier llm` used to run the xplainnlp-nslp preset exactly as defined (a local LM Studio model,
ClimateBERT gate off) with no way to choose another preset, model or provider or to turn the gate on.
"""

from unittest.mock import patch

from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()

_PATCHES = (
    "climafactskg.collectors.cimplekg.fetch_claims",
    "climafactskg.collectors.climatesensekg.fetch_claims",
    "climafactskg.collectors.skepticalscience.fetch_misinformers_urls",
    "climafactskg.collectors.skepticalscience.fetch_arguments_urls",
    "climafactskg.collectors.skepticalscience.process_misinformers_urls",
    "climafactskg.collectors.skepticalscience.process_skstiptionary",
)


def _invoke(args):
    """Runs `process` with every network fetch and every collector stubbed; returns the three process_all mocks."""
    with (
        patch(_PATCHES[0]),
        patch(_PATCHES[1]),
        patch(_PATCHES[2]),
        patch(_PATCHES[3]),
        patch(_PATCHES[4]),
        patch(_PATCHES[5]),
        patch("climafactskg.collectors.cimplekg.process_all") as cimplekg,
        patch("climafactskg.collectors.climatesensekg.process_all") as climatesensekg,
        patch("climafactskg.collectors.skepticalscience.process_all") as sks,
        patch("preserve.open"),
    ):
        result = runner.invoke(app, ["process", *args])
    return result, (cimplekg, climatesensekg, sks)


def test_llm_options_are_forwarded_to_every_source():
    result, mocks = _invoke(
        [
            "--classifier",
            "llm",
            "--preset",
            "cards-narrative",
            "--provider",
            "openrouter",
            "--model",
            "google/gemma-4-31b-it",
            "--preclassifier",
        ]
    )

    assert result.exit_code == 0, result.output
    for mock in mocks:
        assert mock.call_args.kwargs["llm_options"] == {
            "preset": "cards-narrative",
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it",
            "use_preclassifier": True,
        }


def test_no_preclassifier_turns_the_gate_off_explicitly():
    result, mocks = _invoke(["--classifier", "llm", "--no-preclassifier"])

    assert result.exit_code == 0, result.output
    for mock in mocks:
        assert mock.call_args.kwargs["llm_options"] == {"use_preclassifier": False}


def test_without_llm_options_the_preset_runs_as_defined():
    result, mocks = _invoke(["--classifier", "llm"])

    assert result.exit_code == 0, result.output
    for mock in mocks:
        assert mock.call_args.kwargs["llm_options"] is None


def test_llm_options_with_the_transformer_engine_are_rejected():
    result, mocks = _invoke(["--provider", "openrouter"])

    assert result.exit_code == 2
    assert "--classifier llm" in result.output
    for mock in mocks:
        assert not mock.called
