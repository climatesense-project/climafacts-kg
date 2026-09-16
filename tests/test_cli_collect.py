"""Tests for climafactskg.cli's `collect` command.

Covers the per-step failure isolation: one collector raising must not stop
the remaining, independent collectors from running (the same gap `process()`
already closed — a live 504 from CimpleKG's SPARQL endpoint once took down
the entire `collect` run before this fix).
"""

from unittest.mock import patch

from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_collect_continues_after_one_step_fails():
    with (
        patch(
            "climafactskg.collectors.skepticalscience.fetch_arguments_urls",
            side_effect=RuntimeError("simulated failure"),
        ),
        patch("climafactskg.collectors.skepticalscience.fetch_misinformers_urls") as misinformers,
        patch("climafactskg.collectors.cimplekg.fetch_claims") as cimplekg,
        patch("climafactskg.collectors.climatesensekg.fetch_claims") as climatesensekg,
        patch("climafactskg.collectors.skepticalscience.fetch_skstiptionary") as skstiptionary,
    ):
        result = runner.invoke(app, ["collect"])

    assert result.exit_code == 0
    assert misinformers.called
    assert cimplekg.called
    assert climatesensekg.called
    assert skstiptionary.called


def test_collect_runs_all_steps_on_success():
    with (
        patch("climafactskg.collectors.skepticalscience.fetch_arguments_urls") as arguments,
        patch("climafactskg.collectors.skepticalscience.fetch_misinformers_urls") as misinformers,
        patch("climafactskg.collectors.cimplekg.fetch_claims") as cimplekg,
        patch("climafactskg.collectors.climatesensekg.fetch_claims") as climatesensekg,
        patch("climafactskg.collectors.skepticalscience.fetch_skstiptionary") as skstiptionary,
    ):
        result = runner.invoke(app, ["collect"])

    assert result.exit_code == 0
    for mock in (arguments, misinformers, cimplekg, climatesensekg, skstiptionary):
        assert mock.called
