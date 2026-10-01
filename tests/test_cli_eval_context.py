"""Tests for climafactskg.cli's `eval-context` command (builds the review-context sidecar for an eval dataset)."""

from unittest.mock import patch

import pandas as pd
from climafactskg.cli import app
from typer.testing import CliRunner

runner = CliRunner()
BUILDER = "climafactskg.classifiers.cards.context.build_climatesense_context"


def _sidecar(n: int) -> pd.DataFrame:
    return pd.DataFrame({"document_id": [f"id{i}" for i in range(n)], "context_source": "cimplekg", "context": "text"})


def test_builds_the_sidecar_for_the_requested_round():
    with patch(BUILDER, return_value=_sidecar(2)) as build:
        result = runner.invoke(app, ["eval-context", "v2"])

    assert result.exit_code == 0
    build.assert_called_once_with("v2", force=False)


def test_force_flag_rebuilds():
    with patch(BUILDER, return_value=_sidecar(1)) as build:
        result = runner.invoke(app, ["eval-context", "v1", "--force"])

    assert result.exit_code == 0
    build.assert_called_once_with("v1", force=True)


def test_unknown_round_fails_without_building():
    with patch(BUILDER) as build:
        result = runner.invoke(app, ["eval-context", "v3"])

    assert result.exit_code != 0
    build.assert_not_called()
