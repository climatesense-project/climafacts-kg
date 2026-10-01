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

    assert "Relatedness" not in plain
    assert "Relatedness" in mixed and "0.850" in mixed and "0.200" in mixed
