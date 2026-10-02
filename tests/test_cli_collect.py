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


def test_collect_continues_after_one_step_fails_and_then_exits_non_zero():
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

    assert result.exit_code == 1  # the remaining steps ran, but the failure is not hidden from scripts and CI
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


def test_the_failure_exit_helper_is_silent_on_success_and_exits_one_otherwise():
    import pytest
    import typer
    from climafactskg.cli import _exit_if_failed

    _exit_if_failed([], 5)  # nothing failed: returns normally
    with pytest.raises(typer.Exit) as info:
        _exit_if_failed(["a", "b"], 5)
    assert info.value.exit_code == 1
