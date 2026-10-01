"""Tests for evaluating with and without review context (stub classifier, no models, no network)."""

import io
import logging
import re

import pandas as pd
from climafactskg.classifiers.cards import eval as eval_module
from climafactskg.classifiers.cards.base import CARDSClassifierBase
from climafactskg.classifiers.cards.eval import (
    CARDSInput,
    benchmark_configs,
    evaluate,
    print_benchmark,
    print_context_effect,
)
from climafactskg.classifiers.cards.evaluators import (
    CARDSHierarchicalMatch,
    CARDSOneOfMatch,
    HierarchicalMetricsReportEvaluator,
)
from climafactskg.classifiers.cards.runs import CASE_COLUMNS
from pydantic_evals import Case, Dataset
from rich.console import Console


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


class _Plain:
    """Duck-typed classifier: not a CARDSClassifierBase, so it never receives context."""

    def classify(self, text, context=None):
        return "1_1"


class TestClaimOnlyNote:
    def test_not_printed_when_the_classifier_never_receives_context(self, capsys):
        evaluate(_Plain(), _dataset("d", ["ctx a"]))
        assert "claim text only" not in " ".join(capsys.readouterr().out.split())

    def test_printed_when_context_reaches_the_classifier(self, capsys):
        evaluate(_Recorder(), _dataset("d", ["ctx a"]))
        assert "claim text only" in " ".join(capsys.readouterr().out.split())


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


class TestCoverageWarning:
    def test_warns_when_few_cases_carry_context(self, caplog):
        clf = _Recorder()
        with caplog.at_level(logging.WARNING):
            benchmark_configs({"stub": clf}, {"sparse": _dataset("d", ["ctx", None, None])})

        assert any("only_with_context" in r.message and "1 of 3" in r.message for r in caplog.records)

    def test_no_warning_when_coverage_is_high(self, caplog):
        clf = _Recorder()
        with caplog.at_level(logging.WARNING):
            benchmark_configs({"stub": clf}, {"full": _dataset("d", ["a", "b", "c"])})

        assert not [r for r in caplog.records if "only_with_context" in r.message]

    def test_threshold_is_configurable(self, caplog):
        clf = _Recorder()
        with caplog.at_level(logging.WARNING):
            benchmark_configs({"stub": clf}, {"sparse": _dataset("d", ["ctx", None, None])}, min_context_coverage=0.2)

        assert not [r for r in caplog.records if "only_with_context" in r.message]


class TestPrintBenchmark:
    def test_prints_claim_only_note_when_a_with_context_row_exists(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "with", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" in " ".join(capsys.readouterr().out.split())

    def test_no_note_without_with_context_rows(self, capsys):
        df = pd.DataFrame([{"config": "c", "dataset": "d", "context": "none", "n_cases": 2, "exact_match": 1.0}])
        print_benchmark(df)
        assert "claim text only" not in " ".join(capsys.readouterr().out.split())


def _capture(monkeypatch, width=80):
    buffer = io.StringIO()
    monkeypatch.setattr(eval_module, "_console", Console(width=width, file=buffer, color_system=None))
    return buffer


def _long_summary():
    return pd.DataFrame(
        [
            {
                "config": "a-very-long-configuration-label-that-overflows",
                "dataset": "a-very-long-dataset-label",
                "context": "with",
                "n_with_context": 143,
                "n_cases": 143,
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "prompt": "# CARDS TAXONOMY REASONING system prompt",
                "exact_match": 0.378,
                "exact_lo": 0.30,
                "exact_hi": 0.46,
                "h_f1": 0.6084,
                "h_f1_lo": 0.55,
                "h_f1_hi": 0.66,
                "d1_macro_f1": 0.6848,
                "d1_weighted_f1": 0.7,
                "d2_macro_f1": 0.3031,
                "d2_weighted_f1": 0.35,
                "error": "",
            }
        ]
    )


class TestCompactPrintBenchmark:
    def test_compact_output_fits_80_columns_and_shows_intervals(self, monkeypatch):
        buffer = _capture(monkeypatch)
        print_benchmark(_long_summary())
        lines = buffer.getvalue().splitlines()

        assert max(len(line) for line in lines) <= 80
        text = "\\n".join(lines)
        assert "0.378±0.08" in text
        assert "D2 Mac" in text and "0.303" in text  # the last column must not be cropped away
        assert "Provider" not in text and "Prompt" not in text

    def test_wide_shows_every_column(self, monkeypatch):
        buffer = _capture(monkeypatch, width=250)
        print_benchmark(_long_summary(), wide=True)
        text = buffer.getvalue()

        assert "Provider" in text and "Prompt" in text and "D1 Wt" in text

    def test_rows_without_interval_columns_still_print_plain_values(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary().drop(columns=["exact_lo", "exact_hi", "h_f1_lo", "h_f1_hi"])
        print_benchmark(df)

        assert "0.378" in buffer.getvalue() and "±" not in buffer.getvalue()

    def test_missing_scores_print_a_dash_not_nan(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary()
        df.loc[0, ["exact_match", "exact_lo", "exact_hi"]] = float("nan")
        print_benchmark(df)

        assert "nan" not in buffer.getvalue().lower()


class TestPrintContextEffect:
    def test_prints_the_paired_effect(self, monkeypatch):
        buffer = _capture(monkeypatch, width=80)
        rows = []
        for cid, none_exact, with_exact in (("c1", 0.0, 1.0), ("c2", 1.0, 1.0)):
            for mode, exact in (("none", none_exact), ("with", with_exact)):
                rows.append(
                    {
                        "config": "openai/gpt-4o-mini",
                        "dataset": "climatesense-v2",
                        "context": mode,
                        "case_id": cid,
                        "text": "t",
                        "gold": "1_1",
                        "pred": "1_1",
                        "exact": exact,
                        "hf1": exact,
                        "has_context": True,
                        "gold_d1": "1",
                        "pred_d1": "1",
                    }
                )
        print_context_effect(pd.DataFrame(rows, columns=list(CASE_COLUMNS)))

        text = buffer.getvalue()
        assert "Fixed" in text and "Broken" in text  # no header truncated at 80 columns
        assert re.search(r"\bp\b", text) and "1.000" in text  # fixed 1, broken 0 -> exact McNemar p = 1
        assert "+0.500" in text and "0.500" in text and "1.000" in text
        assert max(len(line) for line in text.splitlines()) <= 80

    def test_prints_a_note_when_nothing_is_paired(self, monkeypatch):
        buffer = _capture(monkeypatch, width=80)
        print_context_effect(pd.DataFrame(columns=list(CASE_COLUMNS)))

        assert "no cases" in buffer.getvalue().lower()


class TestFailedAndEmptyRows:
    def test_failed_rows_print_their_error_under_the_compact_table(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary()
        df.loc[0, ["exact_match", "exact_lo", "exact_hi", "h_f1", "h_f1_lo", "h_f1_hi"]] = float("nan")
        df.loc[0, "error"] = "RuntimeError: something exploded in the classifier"
        print_benchmark(df)
        lines = buffer.getvalue().splitlines()

        assert any("something exploded" in line for line in lines)
        assert max(len(line) for line in lines) <= 80

    def test_evaluations_with_no_cases_print_dashes_not_zeros(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary()
        df.loc[0, ["n_cases", "exact_match", "h_f1", "d1_macro_f1", "d2_macro_f1"]] = [0, 0.0, 0.0, 0.0, 0.0]
        print_benchmark(df)

        assert "0.000" not in buffer.getvalue()


class _Flaky(CARDSClassifierBase):
    """Answers 1_1 for every claim except the second, which fails (None) like an LLM item that ran out of retries."""

    def classify(self, text, context=None):
        return None if text.endswith("1") else "1_1"


class TestEvaluateWithFailedPredictions:
    def test_evaluate_survives_failures_and_says_how_many(self, monkeypatch):
        buffer = _capture(monkeypatch, width=100)

        report = evaluate(_Flaky(), _dataset("d", [None, None, None]))

        assert len(report.cases) == 3
        assert "1 of 3 predictions failed" in " ".join(buffer.getvalue().split())

    def test_report_tables_keep_failures_in_the_denominator(self, monkeypatch):
        buffer = _capture(monkeypatch, width=100)
        dataset = _dataset("d", [None, None, None])
        dataset.report_evaluators.append(HierarchicalMetricsReportEvaluator())

        evaluate(_Flaky(), dataset)

        text = " ".join(buffer.getvalue().split())
        assert "0.6667" in text  # 2 right out of 3, not 2 of the 2 that answered
        assert "Failed predictions (counted as wrong)" in text and "1 of 3" in text
        assert "Exact match (answered only)" in text and "1.0000" in text


class TestFailureColumn:
    def test_compact_table_shows_the_failed_count_within_80_columns(self, monkeypatch):
        buffer = _capture(monkeypatch)
        df = _long_summary()
        df["n_failed"] = 7
        print_benchmark(df)
        lines = buffer.getvalue().splitlines()

        assert any("Fail" in line for line in lines)
        assert max(len(line) for line in lines) <= 80
        text = "\n".join(lines)
        assert "D2 Mac" in text and "0.303" in text  # adding a column must not crop the others


class TestCountColumnsWithErrorRows:
    def test_counts_stay_integers_when_another_row_has_no_value(self, monkeypatch):
        buffer = _capture(monkeypatch)
        ok = _long_summary()
        ok["n_failed"] = 7
        failed = ok.copy()
        failed.loc[0, ["n_failed", "exact_match", "h_f1"]] = float("nan")
        failed.loc[0, "error"] = "RuntimeError: boom"
        failed["config"] = "broken"
        df = pd.concat([ok, failed], ignore_index=True)
        print_benchmark(df)
        text = buffer.getvalue()

        assert "7.000" not in text and "143.000" not in text
        assert "  7  " in text.replace("|", " ")
