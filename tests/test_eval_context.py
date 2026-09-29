"""Tests for evaluating with and without review context (stub classifier, no models, no network)."""

import pandas as pd
from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import CARDSInput, benchmark_configs, evaluate, print_benchmark
from climafactskg.classifiers.cards.evaluators import CARDSHierarchicalMatch, CARDSOneOfMatch
from pydantic_evals import Case, Dataset


class _Recorder(CARDSClassifierBase):
    """Always answers 1_1 and records the context each item was classified with."""

    def __init__(self):
        self.seen: list[str | None] = []

    def classify(self, text, context=None):
        self.seen.append(context)
        return "1_1"


def _dataset(name, contexts):
    cases = [
        Case(name=f"case{i}", inputs=CARDSInput(text=f"claim {i}", context=ctx), expected_output=["1_1"])
        for i, ctx in enumerate(contexts)
    ]
    return Dataset(cases=cases, name=name, evaluators=[CARDSOneOfMatch(), CARDSHierarchicalMatch()])


class TestEvaluateUseContext:
    def test_use_context_true_passes_contexts(self):
        clf = _Recorder()
        evaluate(clf, _dataset("d", ["ctx a", None, "ctx c"]), use_context=True)
        assert clf.seen == ["ctx a", None, "ctx c"]

    def test_use_context_false_passes_none_even_when_present(self):
        clf = _Recorder()
        report = evaluate(clf, _dataset("d", ["ctx a", "ctx b"]), use_context=False)
        assert clf.seen == [None, None]
        assert len(report.cases) == 2  # scoring still finds every case's prediction

    def test_default_keeps_using_context(self):
        clf = _Recorder()
        evaluate(clf, _dataset("d", ["ctx a"]))
        assert clf.seen == ["ctx a"]


class TestBenchmarkContextModes:
    def test_runs_both_modes_when_a_dataset_has_context(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"with_ctx": _dataset("d", ["ctx a", "ctx b"])})

        assert list(df["context"]) == ["none", "with"]
        assert list(df["n_cases"]) == [2, 2]
        assert clf.seen == [None, None, "ctx a", "ctx b"]

    def test_reports_how_many_cases_actually_had_context(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"d": _dataset("d", ["ctx a", None, "ctx c"])})

        assert list(df["context"]) == ["none", "with"]
        assert list(df["n_with_context"]) == [0, 2]  # the "with" row is only partly with context

    def test_skips_with_mode_for_datasets_without_context(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"plain": _dataset("d", [None, None])})

        assert list(df["context"]) == ["none"]

    def test_context_modes_can_be_restricted(self):
        clf = _Recorder()
        df = benchmark_configs({"stub": clf}, {"d": _dataset("d", ["ctx"])}, context_modes=("with",))

        assert list(df["context"]) == ["with"]
        assert clf.seen == ["ctx"]


class TestPrintBenchmark:
    def test_prints_claim_only_note_when_a_with_context_row_exists(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "with", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" in " ".join(capsys.readouterr().out.split())

    def test_no_note_without_with_context_rows(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "none", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" not in " ".join(capsys.readouterr().out.split())
