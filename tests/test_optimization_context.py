"""The prompt optimizer must not silently train on review context that eval sidecars add to the datasets."""

import pytest
from pydantic_evals import Case, Dataset

pytest.importorskip("gepa")

from climafactskg.classifiers.cards import datasets  # noqa: E402
from climafactskg.classifiers.cards.datasets import CARDSInput  # noqa: E402
from climafactskg.classifiers.cards.optimization import build_mixed_trainval  # noqa: E402


def test_mixed_trainval_loads_climatesense_datasets_without_context(monkeypatch):
    seen: dict[str, dict] = {}

    def fake_factory(name):
        def factory(**kwargs):
            seen[name] = kwargs
            return Dataset(cases=[Case(name=f"case-{name}", inputs=CARDSInput(text="claim"), expected_output=["1_1"])])

        return factory

    monkeypatch.setattr(datasets, "climatesense_dataset_v1", fake_factory("cs_v1"))
    monkeypatch.setattr(datasets, "climatesense_dataset_v2", fake_factory("cs_v2"))

    build_mixed_trainval({"cs_v1": (1, 0), "cs_v2": (1, 0)})

    for name in ("cs_v1", "cs_v2"):
        assert seen[name].get("with_context") is False, f"{name} must be loaded explicitly claim-only"
        assert seen[name].get("context_path") is None
