"""HTML report: sections, escaping, valid inline SVG, themes, multi-run handling, failed rows."""

import re
import xml.etree.ElementTree as ET

import pandas as pd
import pytest
from climafactskg.classifiers.cards.report import bar_chart_svg, render_html
from climafactskg.classifiers.cards.runs import CASE_COLUMNS, BenchmarkRun


def _summary_row(config="gpt", dataset="d", context="none", exact=0.4, hf1=0.6, error="", n=10, n_ctx=10):
    ok = not error
    nan = float("nan")
    return {
        "config": config,
        "dataset": dataset,
        "context": context,
        "n_with_context": n_ctx,
        "n_cases": n if ok else 0,
        "exact_match": exact if ok else nan,
        "exact_lo": exact - 0.1 if ok else nan,
        "exact_hi": exact + 0.1 if ok else nan,
        "h_f1": hf1 if ok else nan,
        "h_f1_lo": hf1 - 0.1 if ok else nan,
        "h_f1_hi": hf1 + 0.1 if ok else nan,
        "d1_macro_f1": 0.5 if ok else nan,
        "d2_macro_f1": 0.3 if ok else nan,
        "error": error,
    }


def _case(config, context, case_id, exact, pred="1_1", text="a claim"):
    return {
        "config": config,
        "dataset": "d",
        "context": context,
        "case_id": case_id,
        "text": text,
        "gold": "1_1",
        "pred": pred,
        "exact": exact,
        "hf1": exact,
        "has_context": True,
        "gold_d1": "1",
        "pred_d1": pred[0],
    }


def _run(run_id="20260929T000000Z-abc123", config="gpt", with_context=True, extra_summary=(), text="a claim"):
    summary = [_summary_row(config=config, context="none")]
    cases = [_case(config, "none", "c1", 0.0, "2_1", text), _case(config, "none", "c2", 1.0)]
    if with_context:
        summary.append(_summary_row(config=config, context="with", exact=0.6))
        cases += [_case(config, "with", "c1", 1.0, "1_1", text), _case(config, "with", "c2", 0.0, "2_1")]
    summary.extend(extra_summary)
    return BenchmarkRun(
        meta={
            "run_id": run_id,
            "created_at": "2026-09-29T00:00:00+00:00",
            "git_commit": "deadbeef",
            "package_version": "2.1.4",
            "datasets": [{"name": "d", "n_cases": 2, "n_with_context": 2}],
            "configs": [{"label": config, "provider": "p", "model": "m", "prompt": "pr"}],
        },
        summary=pd.DataFrame(summary),
        cases=pd.DataFrame(cases, columns=list(CASE_COLUMNS)),
    )


def _svgs(html):
    return re.findall(r"<svg.*?</svg>", html, flags=re.DOTALL)


class TestBarChartSvg:
    def test_is_well_formed_xml_with_bars_and_a_title(self):
        svg = bar_chart_svg(
            "Exact match",
            ["d1", "d2"],
            ["a", "b"],
            [[0.4, 0.5], [0.6, 0.2]],
            [[0.3, 0.4], [0.5, 0.1]],
            [[0.5, 0.6], [0.7, 0.3]],
        )
        root = ET.fromstring(svg)

        assert root.tag.endswith("svg")
        assert len(root.findall(".//{*}path[@class]")) >= 4
        assert "Exact match" in svg

    def test_missing_values_are_omitted_without_error(self):
        svg = bar_chart_svg("t", ["d"], ["a", "b"], [[float("nan")], [0.5]])
        ET.fromstring(svg)
        assert "nan" not in svg.lower()

    def test_tied_best_bars_share_one_value_label_per_group(self):
        svg = bar_chart_svg("t", ["g1", "g2"], ["a", "b", "c"], [[0.3, 0.5], [0.3, 0.4], [0.3, 0.5]])

        assert svg.count('class="best"') == 2  # one label per group, even when several bars tie for best

    def test_escapes_labels(self):
        svg = bar_chart_svg("<b>t</b>", ["<g>"], ["<s>"], [[0.5]])
        ET.fromstring(svg)
        assert "<b>t</b>" not in svg


class TestRenderHtml:
    def test_writes_a_self_contained_report_with_expected_sections(self, tmp_path):
        out = render_html([_run()], tmp_path / "report.html")
        html = out.read_text(encoding="utf-8")

        for heading in ("Comparison", "Context effect", "Run details"):
            assert f"<h2>{heading}</h2>" in html
        assert "claim text only" in html
        assert "prefers-color-scheme: dark" in html
        assert not re.search(r'(?:src|href)="http|@import|url\(http', html)
        assert "<script" not in html

    def test_every_svg_is_valid_xml(self, tmp_path):
        html = render_html([_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        svgs = _svgs(html)
        assert len(svgs) >= 3
        for svg in svgs:
            ET.fromstring(svg)

    def test_html_special_characters_are_escaped(self, tmp_path):
        evil = '<script>alert(1)</script> & "quoted"'
        html = render_html([_run(config="<img src=x>", text=evil)], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "<script>alert(1)" not in html
        assert "<img src=x>" not in html
        assert "&lt;script&gt;" in html

    def test_context_sections_are_skipped_without_paired_data(self, tmp_path):
        html = render_html([_run(with_context=False)], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "<h2>Context effect</h2>" not in html
        assert "<h2>Comparison</h2>" in html

    def test_failed_combination_is_flagged_and_does_not_break_the_report(self, tmp_path):
        failed = _summary_row(config="broken", error="RuntimeError: boom")
        html = render_html([_run(extra_summary=[failed])], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "RuntimeError: boom" in html
        assert "nan" not in html.lower().replace("nanosecond", "")

    def test_identical_config_labels_across_runs_do_not_collide(self, tmp_path):
        html = render_html([_run("20260101T000000Z-aaaaaa"), _run("20260202T000000Z-bbbbbb")], tmp_path / "r.html")
        text = html.read_text(encoding="utf-8")

        assert "gpt (20260101T000000Z-aaaaaa)" in text and "gpt (20260202T000000Z-bbbbbb)" in text

    def test_creates_parent_directories_and_leaves_no_temp_file(self, tmp_path):
        out = render_html([_run()], tmp_path / "nested" / "dir" / "report.html")

        assert out.is_file()
        assert [p.name for p in out.parent.iterdir()] == ["report.html"]

    def test_requires_at_least_one_run(self, tmp_path):
        with pytest.raises(ValueError):
            render_html([], tmp_path / "r.html")


class TestReviewFixes:
    def test_runs_minutes_apart_do_not_collide(self, tmp_path):
        from climafactskg.classifiers.cards.report import _combine
        from climafactskg.classifiers.cards.runs import context_effect

        first, second = _run("20260929T121503Z-aaaaaa"), _run("20260929T121803Z-bbbbbb")
        summary, cases = _combine([first, second])

        assert len(set(summary["config"])) == 2
        effect = context_effect(cases)
        assert sorted(effect["n_paired"]) == [2, 2]  # each run pairs only its own two cases
        html = render_html([first, second], tmp_path / "r.html").read_text(encoding="utf-8")
        assert "20260929T121503Z-aaaaaa" in html and "20260929T121803Z-bbbbbb" in html

    def test_identical_run_ids_still_get_distinct_labels(self):
        from climafactskg.classifiers.cards.report import _combine

        summary, _ = _combine([_run("same-id"), _run("same-id")])

        assert len(set(summary["config"])) == 2

    def test_evaluations_with_no_cases_show_dashes_not_zeros(self, tmp_path):
        row = _summary_row(config="empty", dataset="nothing", n=0)
        row.update({"n_cases": 0, "exact_match": 0.0, "h_f1": 0.0, "d1_macro_f1": 0.0, "d2_macro_f1": 0.0})
        run = BenchmarkRun(
            meta={"run_id": "r1", "datasets": [], "configs": []},
            summary=pd.DataFrame([row]),
            cases=pd.DataFrame(columns=list(CASE_COLUMNS)),
        )
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "0.000" not in html

    def test_changed_cases_table_names_the_dataset(self, tmp_path):
        html = render_html([_run()], tmp_path / "r.html").read_text(encoding="utf-8")

        section = html[html.index("Cases changed by context") :]
        assert "<th>Dataset</th>" in section.split("</table>")[0]


class TestReliabilityColumns:
    def _extended_run(self):
        run = _run()
        run.summary["n_failed"] = [3, 0]
        run.summary["not_related_rate"] = [0.28, 0.15]
        run.summary["exact_unambiguous"] = [0.4156, 0.3117]
        run.summary["n_unambiguous"] = [77, 77]
        run.summary["baseline_exact"] = [0.1958, 0.1958]
        run.summary["d2_macro_f1_lo"] = [0.23, 0.2]
        run.summary["d2_macro_f1_hi"] = [0.35, 0.34]
        return run

    def test_comparison_table_shows_failures_baseline_and_the_unambiguous_subset(self, tmp_path):
        html = render_html([self._extended_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        table = html[html.index("<h2>Comparison</h2>") : html.index("<h2>Charts</h2>")]

        for header in ("Failed", "Not related", "Unambiguous", "Baseline"):
            assert f'<th class="num">{header}</th>' in table
        assert "28%" in table and "0.196" in table and "0.416" in table and "n=77" in table
        assert "3 failed" in table  # the note cell says failures are counted as wrong

    def test_macro_f1_gets_its_interval_in_the_table(self, tmp_path):
        html = render_html([self._extended_run()], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "[0.23–0.35]" in html

    def test_older_runs_without_the_new_columns_still_render(self, tmp_path):
        html = render_html([_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        table = html[html.index("<h2>Comparison</h2>") : html.index("<h2>Charts</h2>")]

        assert table.count("—") >= 4  # failed / not related / unambiguous / baseline are dashes, not made-up values
        assert "nan" not in html.lower()


def _two_config_run():
    ids = [f"c{i}" for i in range(10)]
    cases = []
    for config, right in (("A", ids[:5]), ("B", ids[:9])):
        for cid in ids:
            cases.append(_case(config, "none", cid, 1.0 if cid in right else 0.0))
    summary = [_summary_row(config="A", context="none", exact=0.5), _summary_row(config="B", context="none", exact=0.9)]
    run = _run(with_context=False)
    run.summary = pd.DataFrame(summary)
    run.cases = pd.DataFrame(cases, columns=list(CASE_COLUMNS))
    return run


class TestSignificanceInReport:
    def test_context_effect_table_has_an_interval_and_a_p_value(self, tmp_path):
        html = render_html([_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        section = html[html.index("<h2>Context effect</h2>") :]

        assert '<th class="num">\u0394 95% CI</th>' in section and '<th class="num">p</th>' in section
        assert "McNemar" in section

    def test_two_configs_get_a_model_comparison_against_the_first(self, tmp_path):
        html = render_html([_two_config_run()], tmp_path / "r.html").read_text(encoding="utf-8")
        section = html[html.index("<h2>Model comparison</h2>") :]

        assert "<b>A</b>" in section  # the baseline defaults to the first config
        assert "0.125" in section  # 4 better, 0 worse -> exact p = 2 * (1/2)^4
        assert "+0.400" in section and "not corrected" in section

    def test_a_single_config_has_no_model_comparison(self, tmp_path):
        html = render_html([_run(with_context=False)], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "Model comparison" not in html

    def test_the_baseline_can_be_chosen(self, tmp_path):
        html = render_html([_two_config_run()], tmp_path / "r.html", baseline="B").read_text(encoding="utf-8")
        section = html[html.index("<h2>Model comparison</h2>") :]

        assert "<b>B</b>" in section and "-0.400" in section

    def test_an_unknown_baseline_is_a_clear_error(self, tmp_path):
        with pytest.raises(ValueError, match="baseline"):
            render_html([_two_config_run()], tmp_path / "r.html", baseline="nope")


def test_relatedness_section_appears_only_when_a_run_has_not_climate_documents(tmp_path):
    plain = render_html([_run()], tmp_path / "plain.html").read_text(encoding="utf-8")
    row = {
        **_summary_row(),
        "n_not_climate": 6,
        "rel_precision": 0.8,
        "rel_recall": 0.9,
        "rel_f1": 0.85,
        "rel_fpr": 0.2,
    }
    mixed = render_html([_run(extra_summary=[row])], tmp_path / "mixed.html").read_text(encoding="utf-8")

    assert "Narrative detection" not in plain
    assert "Narrative detection" in mixed and "0.850" in mixed and "0.200" in mixed


_REPEAT = {
    "n_not_climate": 6,
    "rel_precision": 0.8,
    "rel_recall": 0.9,
    "rel_f1": 0.85,
    "rel_fpr": 0.2,
}


class TestReadability:
    def _html(self, tmp_path, run):
        return render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

    def test_at_a_glance_comes_first_and_states_the_best_result_and_the_context_verdict(self, tmp_path):
        html = self._html(tmp_path, _run())
        section = html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

        assert "gpt" in section and "0.600" in section  # best exact match, reached with context
        assert "within noise" in section  # one case fixed, one broken: no real effect

    def test_at_a_glance_summarises_each_model_against_the_baseline(self, tmp_path):
        html = self._html(tmp_path, _two_config_run())
        section = html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

        assert "B" in section and "+0.400" in section

    def test_a_collapsible_glossary_defines_the_metrics_without_javascript(self, tmp_path):
        html = self._html(tmp_path, _run())
        glossary = html[html.index("<details><summary>How to read this report") :]
        glossary = glossary[: glossary.index("</details>")]

        for term in ("Exact", "hF1", "D1 macro", "D2 macro", "Failed", "Baseline", "p-value"):
            assert term in glossary
        assert "<script" not in html

    def test_the_main_table_keeps_the_core_columns_and_the_reliability_table_the_rest(self, tmp_path):
        html = self._html(tmp_path, _run())
        table = html[html.index("<h2>Comparison</h2>") : html.index("<h3>Reliability</h3>")]
        rest = html[html.index("<h3>Reliability</h3>") : html.index("<h2>Charts</h2>")]

        assert "Unambiguous" not in table and "Baseline" not in table and "With ctx" not in table
        assert all(f'<th class="num">{h}</th>' in rest for h in ("Not related", "Unambiguous", "Baseline"))
        assert "D2 macro" in table

    def _with_repeat_cases(self, run, dataset="mixed", same_cases=True):
        """Adds case rows for *dataset*: the same cases as dataset 'd' (a repeat) or different ones."""
        rows = run.cases[run.cases["dataset"] == "d"].copy()
        rows["dataset"] = dataset
        if not same_cases:
            rows["case_id"] = rows["case_id"] + "-other"
            rows["text"] = rows["text"] + " (a different claim)"
        run.cases = pd.concat([run.cases, rows], ignore_index=True)
        return run

    def test_datasets_with_equal_scores_but_different_cases_are_not_folded_together(self, tmp_path):
        repeat = {**_summary_row(dataset="mixed", context="none"), **_REPEAT}
        run = self._with_repeat_cases(_run(with_context=False, extra_summary=[repeat]), same_cases=False)
        html = self._html(tmp_path, run)
        category_part = html[html.index("<h2>Comparison</h2>") : html.index("<h2>Narrative detection</h2>")]

        assert "<td>mixed</td>" in category_part  # identical numbers on different claims is not a repeat
        assert "repeats the category scores" not in html

    def test_without_case_rows_nothing_is_folded(self, tmp_path):
        repeat = {**_summary_row(dataset="mixed", context="none"), **_REPEAT}
        html = self._html(tmp_path, _run(with_context=False, extra_summary=[repeat]))

        assert "repeats the category scores" not in html

    def test_a_dataset_that_repeats_another_datasets_category_scores_is_shown_once(self, tmp_path):
        repeat = {**_summary_row(dataset="mixed", context="none"), **_REPEAT}
        run = self._with_repeat_cases(_run(with_context=False, extra_summary=[repeat]))
        html = self._html(tmp_path, run)
        category_part = html[html.index("<h2>Comparison</h2>") : html.index("<h2>Narrative detection</h2>")]
        charts = html[html.index("<h2>Charts</h2>") :]

        assert "<td>mixed</td>" not in category_part and "mixed" not in charts.split("<h2>Run details</h2>")[0]
        assert "mixed" in html[html.index("<h2>Narrative detection</h2>") : html.index("<h2>Charts</h2>")]
        assert "repeat" in category_part  # a note says which dataset was folded away

    def test_narrative_detection_is_described_as_denial_narrative_versus_none(self, tmp_path):
        row = {**_summary_row(dataset="mixed"), **_REPEAT}
        html = self._html(tmp_path, _run(with_context=False, extra_summary=[row]))
        section = html[html.index("<h2>Narrative detection</h2>") : html.index("<h2>Charts</h2>")]

        assert "0_0" in section and "climate or not" not in section.lower()

    def test_a_tiny_p_value_reads_as_less_than_not_equals_less_than(self):
        from climafactskg.classifiers.cards.report import _p_relation

        assert _p_relation(0.0001) == "< 0.001" and _p_relation(0.125) == "= 0.125"

    def test_verdict_words(self):
        from climafactskg.classifiers.cards.report import _verdict

        assert _verdict(0.3, 0.001) == "significantly better"
        assert _verdict(-0.3, 0.001) == "significantly worse"
        assert _verdict(-0.03, 0.557) == "within noise"
        assert _verdict(0.0, float("nan")) == "—"

    def test_the_model_comparison_says_what_its_p_value_means(self, tmp_path):
        html = self._html(tmp_path, _two_config_run())
        section = html[html.index("<h2>Model comparison</h2>") :]

        assert "<th>Verdict</th>" in section and "within noise" in section  # 4 better, 0 worse: p = 0.125

    def test_the_context_effect_says_what_its_p_value_means(self, tmp_path):
        html = self._html(tmp_path, _run())
        section = html[html.index("<h2>Context effect</h2>") :]

        assert "<th>Verdict</th>" in section and "within noise" in section


class TestBaselineAwareReport:
    def _html(self, tmp_path, run):
        return render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

    def _mixed(self, **extra):
        return {
            **_summary_row(dataset="mixed", context="none", exact=0.45, hf1=0.55),
            "baseline_exact": 0.55,
            "exact_category": 0.7,
            "n_category": 6,
            **_REPEAT,
            **extra,
        }

    def test_a_score_at_or_below_the_always_guess_baseline_is_called_out(self, tmp_path):
        html = self._html(tmp_path, _run(with_context=False, extra_summary=[self._mixed()]))
        section = html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

        assert "no better than always guessing" in section and "0.550" in section

    def test_the_zero_zero_remark_only_appears_for_datasets_that_have_such_documents(self, tmp_path):
        weak = _summary_row(dataset="plain", context="none", exact=0.1, hf1=0.2)
        html = self._html(tmp_path, _run(with_context=False, extra_summary=[{**weak, "baseline_exact": 0.3}]))
        section = html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

        assert "no better than always guessing" in section and "that label is 0_0" not in section

    def test_a_score_above_the_baseline_is_not_flagged(self, tmp_path):
        html = self._html(tmp_path, _run(with_context=False, extra_summary=[self._mixed(baseline_exact=0.2)]))
        section = html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

        assert "no better than always guessing" not in section

    def test_the_category_case_exact_column_appears_only_when_there_are_not_climate_documents(self, tmp_path):
        plain = self._html(tmp_path, _run(with_context=False))
        mixed = self._html(tmp_path, _run(with_context=False, extra_summary=[self._mixed()]))

        header = '<th class="num">Exact, category cases</th>'
        assert header not in plain
        table = mixed[mixed.index("<h2>Comparison</h2>") : mixed.index("<h3>Reliability</h3>")]
        assert header in table and "0.700" in table

    def test_the_model_comparison_lists_the_baseline_as_a_row(self, tmp_path):
        html = self._html(tmp_path, _two_config_run())
        section = html[html.index("<h2>Model comparison</h2>") :].split("</table>")[0]

        assert "<td>baseline</td>" in section


class TestReportWithAFailedConfig:
    def _run_with_failed(self, failed="A", ok="B"):
        base = _two_config_run()
        summary = pd.DataFrame([_summary_row(config=failed, error="boom"), _summary_row(config=ok)])
        cases = base.cases[base.cases["config"] == ok].reset_index(drop=True)
        return BenchmarkRun(meta=base.meta, summary=summary, cases=cases)

    def test_a_failed_first_config_does_not_break_the_report(self, tmp_path):
        html = render_html([self._run_with_failed()], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "failed: boom" in html  # the failure is still shown
        assert "<h2>Comparison</h2>" in html

    def test_an_explicit_baseline_without_results_is_explained_not_raised(self, tmp_path):
        html = render_html([self._run_with_failed()], tmp_path / "r.html", baseline="A").read_text(encoding="utf-8")
        section = html[html.index("<h2>Model comparison</h2>") :]

        assert "no results" in section.split("<h2>")[1]

    def test_the_default_baseline_skips_a_config_without_results(self, tmp_path):
        base = _two_config_run()
        summary = pd.concat([pd.DataFrame([_summary_row(config="Z", error="boom")]), base.summary], ignore_index=True)
        run = BenchmarkRun(meta=base.meta, summary=summary, cases=base.cases)
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "<b>A</b>" in html[html.index("<h2>Model comparison</h2>") :]


def _sized_run(models, dataset="d", **extra):
    """A run with one 'none' row per model: models maps label -> (size_b, active_b, exact)."""
    summary = [
        {**_summary_row(config=label, dataset=dataset, context="none", exact=exact), **extra}
        for label, (_, _, exact) in models.items()
    ]
    configs = [
        {"label": label, "provider": "p", "model": "m", "prompt": "x", "size_b": size, "active_b": active}
        for label, (size, active, _) in models.items()
    ]
    run = _run(with_context=False)
    run.summary = pd.DataFrame(summary)
    run.cases = run.cases.iloc[0:0]
    run.meta = {**run.meta, "configs": configs, "datasets": [{"name": dataset, "n_cases": 10, "n_with_context": 0}]}
    return run


class TestSizePlot:
    def test_the_frontier_keeps_models_that_no_smaller_model_beats(self):
        from climafactskg.classifiers.cards.report import _pareto_front

        points = [(10, 0.4), (20, 0.35), (30, 0.5), (30, 0.45), (5, 0.2)]

        assert [points[i] for i in _pareto_front(points)] == [(5, 0.2), (10, 0.4), (30, 0.5)]

    def test_the_scatter_is_valid_svg_with_log_ticks_labels_and_a_moe_hover(self):
        from climafactskg.classifiers.cards.report import size_scatter_svg

        points = [
            {"label": "small", "size": 8.0, "active": None, "value": 0.3, "lo": 0.2, "hi": 0.4, "flag": False},
            {"label": "moe <b>", "size": 235.0, "active": 22.0, "value": 0.6, "lo": 0.5, "hi": 0.7, "flag": True},
        ]
        svg = size_scatter_svg("t", points)

        ET.fromstring(svg)
        assert "small" in svg and "moe &lt;b&gt;" in svg and "<b>" not in svg
        assert "235B (22B active)" in svg
        assert ">10B<" in svg and ">100B<" in svg

    def test_the_section_appears_when_two_or_more_models_have_a_size(self, tmp_path):
        run = _sized_run({"A": (8.0, None, 0.3), "B": (70.0, None, 0.5), "C": (None, None, 0.6)})
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")
        section = html[html.index("<h2>Size and result</h2>") :].split("<h2>")[1]

        assert "<svg" in section
        assert "No published size" in section and "C" in section  # listed, not silently dropped

    def test_one_sized_model_is_not_a_plot(self, tmp_path):
        run = _sized_run({"A": (8.0, None, 0.3), "B": (None, None, 0.5)})
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "Size and result" not in html

    def test_runs_saved_before_sizes_existed_have_no_section(self, tmp_path):
        html = render_html([_two_config_run()], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "Size and result" not in html

    def test_heavily_failed_models_are_marked(self, tmp_path):
        run = _sized_run({"A": (8.0, None, 0.3), "B": (70.0, None, 0.5)})
        run.summary["n_failed"] = [0, 6]  # 6 of 10 failed
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")

        assert "failed on more than 10%" in html


class TestRankedBars:
    def test_models_are_listed_best_first_with_escaped_labels_and_values(self):
        from climafactskg.classifiers.cards.report import ranked_bars_svg

        items = [("low <i>", 0.2, 0.1, 0.3), ("high", 0.8, 0.7, 0.9), ("mid", 0.5, float("nan"), float("nan"))]
        svg = ranked_bars_svg("t", items)

        ET.fromstring(svg)
        assert "<i>" not in svg and "low &lt;i&gt;" in svg
        assert svg.index(">high<") < svg.index(">mid<") < svg.index(">low &lt;i&gt;<")
        assert "0.80" in svg

    def test_many_models_get_a_ranked_chart_instead_of_dropping_series(self, tmp_path):
        models = {f"M{i}": (None, None, 0.1 + 0.05 * i) for i in range(10)}
        html = render_html([_sized_run(models)], tmp_path / "r.html").read_text(encoding="utf-8")
        charts = html[html.index("<h2>Charts</h2>") :].split("<h2>")[1]

        assert "further series are not drawn" not in html
        assert all(f">M{i}<" in charts for i in range(10))  # every model is drawn, without a redundant suffix

    def test_few_models_keep_the_grouped_bars(self, tmp_path):
        html = render_html([_two_config_run()], tmp_path / "r.html").read_text(encoding="utf-8")

        assert 'class="legend"' in html


class TestGlanceWithManyModels:
    def _glance(self, tmp_path, n_models):
        run = _run(with_context=False)
        cases, summary = [], []
        ids = [f"c{i}" for i in range(10)]
        for k in range(n_models):
            label = f"M{k}"
            right = ids[
                : 5 if k == 0 else (5 if k % 2 else 10)
            ]  # M0 baseline; odd models tie it, even ones are far better
            summary.append(_summary_row(config=label, context="none", exact=len(right) / 10))
            for cid in ids:
                cases.append(_case(label, "none", cid, 1.0 if cid in right else 0.0))
        run.summary = pd.DataFrame(summary)
        run.cases = pd.DataFrame(cases, columns=list(CASE_COLUMNS))
        html = render_html([run], tmp_path / "r.html").read_text(encoding="utf-8")
        return html[html.index("<h2>At a glance</h2>") : html.index("<h2>Comparison</h2>")]

    def test_few_models_are_all_listed(self, tmp_path):
        section = self._glance(tmp_path, 4)

        assert section.count(" against ") == 3

    def test_many_models_list_only_the_significant_ones_and_summarise_the_rest(self, tmp_path):
        section = self._glance(tmp_path, 14)

        assert section.count("<li>") < 14
        assert "within noise" in section and "other model" in section  # one summary line for the rest
