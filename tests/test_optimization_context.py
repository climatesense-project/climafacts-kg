"""The prompt optimizer must not silently train on review context that eval sidecars add to the datasets."""

import pytest
from pydantic_evals import Case, Dataset

pytest.importorskip("gepa")

from climafactskg.classifiers.cards import datasets  # noqa: E402
from climafactskg.classifiers.cards.datasets import CARDSInput  # noqa: E402
from climafactskg.classifiers.cards.optimization import build_heldout, build_mixed_trainval  # noqa: E402


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


def _fake_datasets(monkeypatch, n=10):
    seen: dict[str, dict] = {}

    def fake_factory(name):
        def factory(**kwargs):
            seen[name] = kwargs
            return Dataset(
                cases=[
                    Case(name=f"{name}-{i}", inputs=CARDSInput(text=f"{name} claim {i}"), expected_output=["1_1"])
                    for i in range(n)
                ]
            )

        return factory

    monkeypatch.setattr(datasets, "climatesense_dataset_v1", fake_factory("cs_v1"))
    monkeypatch.setattr(datasets, "climatesense_dataset_v2", fake_factory("cs_v2"))
    monkeypatch.setattr(datasets, "nslp_dataset", fake_factory("nslp"))
    return seen


def test_mixed_trainval_keeps_climate_only_by_default_and_can_include_the_no_narrative_documents(monkeypatch):
    seen = _fake_datasets(monkeypatch)

    build_mixed_trainval({"cs_v1": (1, 0)})
    assert seen["cs_v1"]["climate_only"] is True

    build_mixed_trainval({"cs_v1": (1, 0), "cs_v2": (1, 0)}, climate_only=False)
    assert seen["cs_v1"]["climate_only"] is False
    assert seen["cs_v2"]["climate_only"] is False


def test_mixed_trainval_keeps_file_order_unless_a_seed_is_given(monkeypatch):
    _fake_datasets(monkeypatch)

    train, _ = build_mixed_trainval({"cs_v1": (4, 2)})

    assert [c.name for c in train.cases] == ["cs_v1-0", "cs_v1-1", "cs_v1-2", "cs_v1-3"]


def test_shuffle_seed_is_reproducible_and_changes_the_order(monkeypatch):
    _fake_datasets(monkeypatch)

    first, _ = build_mixed_trainval({"cs_v1": (6, 2)}, shuffle_seed=7)
    again, _ = build_mixed_trainval({"cs_v1": (6, 2)}, shuffle_seed=7)
    other, _ = build_mixed_trainval({"cs_v1": (6, 2)}, shuffle_seed=8)

    assert [c.name for c in first.cases] == [c.name for c in again.cases]
    assert [c.name for c in first.cases] != [c.name for c in other.cases]
    assert [c.name for c in first.cases] != [f"cs_v1-{i}" for i in range(6)]


def test_heldout_is_exactly_what_train_and_val_leave_out(monkeypatch):
    _fake_datasets(monkeypatch)
    mix = {"cs_v1": (3, 2), "nslp": (2, 1)}

    train, val = build_mixed_trainval(mix, shuffle_seed=3)
    heldout = build_heldout(mix, shuffle_seed=3)

    used = [c.name for c in train.cases] + [c.name for c in val.cases]
    left = [c.name for c in heldout.cases]
    assert not set(used) & set(left)
    assert sorted(used + left) == sorted([f"cs_v1-{i}" for i in range(10)] + [f"nslp-{i}" for i in range(10)])


class _StubAgent:
    """Answers "1_1" for every claim except one that raises, to exercise GEPA's per-case failure handling."""

    def __init__(self, failing_claim):
        self.failing_claim = failing_claim

    def override(self, **_kwargs):
        from contextlib import nullcontext

        return nullcontext()

    async def run(self, message, model_settings=None):
        from types import SimpleNamespace

        if self.failing_claim in message:
            raise RuntimeError("provider error")
        return SimpleNamespace(output=SimpleNamespace(is_climate_related=True, cards_category="1_1"))


def _stub_classifier(failing_claim):
    from types import SimpleNamespace

    return SimpleNamespace(
        _agent=_StubAgent(failing_claim),
        _user_prompt="{text}",
        _user_prompt_with_context="{text} {context}",
        _model_settings=None,
        _default_concurrency=2,
    )


def test_a_failed_call_stays_a_wrong_answer_in_its_own_slot():
    from climafactskg.classifiers.cards.optimization import CARDSDataInst, CARDSEvalsAdapter

    batch = [
        CARDSDataInst(claim="claim a", expected=["1_1"]),
        CARDSDataInst(claim="claim b", expected=["1_1"]),
        CARDSDataInst(claim="claim c", expected=["1_1"]),
    ]
    adapter = CARDSEvalsAdapter(_stub_classifier("claim b"))

    result = adapter.evaluate(batch, {"instructions": "prompt"}, capture_traces=True)

    assert result.scores == [1.0, 0.0, 1.0]  # not [1.0, 1.0]: the failure keeps its slot
    assert len(result.outputs) == 3
    assert [t.claim for t in result.trajectories] == ["claim a", "claim b", "claim c"]


def test_a_failed_call_is_not_fed_back_to_the_reflection_model_as_a_wrong_prediction():
    from climafactskg.classifiers.cards.optimization import CARDSDataInst, CARDSEvalsAdapter

    batch = [CARDSDataInst(claim="claim a", expected=["2_1"]), CARDSDataInst(claim="claim b", expected=["1_1"])]
    adapter = CARDSEvalsAdapter(_stub_classifier("claim b"))
    result = adapter.evaluate(batch, {"instructions": "prompt"}, capture_traces=True)

    records = adapter.make_reflective_dataset({"instructions": "prompt"}, result, ["instructions"])["instructions"]

    assert [r["Inputs"]["claim"] for r in records] == ["claim a"]  # a wrong answer; the failure is left out
