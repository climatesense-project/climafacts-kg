# Readable, saved, comparable CARDS evaluation reporting

Status: design, awaiting review. Date: 2026-09-29.

## Goal

Make evaluation results easy to read, keep, compare and visualise, without new dependencies and without adding features
nobody asked for. Today `benchmark_configs` returns a DataFrame that is lost with the terminal, `print_benchmark`
renders 12+ columns that are unreadable at 80 columns, there is no per-case data to look at, and comparing with vs
without context or model vs model means pivoting by hand.

## Decisions (user)

- Every run is **saved**; a self-contained **HTML report** is generated from saved runs.
- Charts are **inline SVG through jinja2** (already installed): no new dependency, no JS, no CDN, light and dark mode.
- "Best approach without bloat": no Markdown variant, no per-class bars, no confusion heatmap, no interactive dashboard.

## Findings that constrain the design

- `benchmark_configs` computes per-case scores (`report.cases[i].scores["CARDSOneOfMatch"]`,
  `["CARDSHierarchicalMatch"]`, plus output and expected output) but only keeps aggregates, so per-case data has to be
  captured inside it.
- Scores are noisy at this sample size (143 cases: standard error of exact match is about 4 points), so point estimates
  alone mislead; a bootstrap interval is cheap (pandas/numpy are already dependencies).
- Datasets can be partly covered by context (`n_with_context`); the honest with/without comparison is on the cases that
  actually have context, so the effect table must be paired on those.
- matplotlib, plotly, seaborn and altair are not installed; jinja2 and rich are.
- `data/*.db` is gitignored but `data/eval_runs/` would not be, so it needs an ignore entry.

## Design

### 1. Saved runs: `climafactskg/classifiers/cards/runs.py` (new)

- `BenchmarkRun` dataclass: `meta: dict`, `summary: pd.DataFrame`, `cases: pd.DataFrame`, `path: Path | None`.
- `save_run(run, base_dir) -> Path` writes `<base_dir>/<UTC timestamp>-<6-char id>/` containing:
  - `run.json`: run id, created_at (UTC ISO), git commit (or `null` outside a repo), package version, datasets
    (name, n_cases, n_with_context), configs (label, provider, model, prompt id), context modes, `min_context_coverage`.
  - `cases.csv` (tidy, one row per case x config x context mode): `config, dataset, context, case_id, text, gold, pred,
    exact, hf1, has_context, gold_d1, pred_d1` (`gold` is `;`-joined).
  - `summary.csv`: the benchmark table plus interval columns.
- Writes are atomic per file (temp file then rename); an existing directory is never overwritten.
- `load_run(path) -> BenchmarkRun` validates that the three files exist and the required columns are present, and raises
  a clear `ValueError` otherwise.
- `bootstrap_ci(values, n_boot=2000, seed=0, level=0.95) -> tuple[float, float]`: deterministic percentile bootstrap of
  the mean.
- `context_effect(cases) -> pd.DataFrame`: per (config, dataset), restricted to cases with `has_context` in the `with`
  run, comparing `none` vs `with` on the same case ids: `n_paired, exact_none, exact_with, delta, fixed, broken,
  unchanged` (fixed: wrong without, right with; broken: the reverse).

### 2. `eval.py`

- Extract the body of the `benchmark_configs` loop into `_run_combo(...)`, which returns the summary row and the
  per-case rows. Behavior of the existing rows and columns is unchanged.
- `benchmark_configs(..., save_dir: str | None = None)`: when set, builds a `BenchmarkRun`, saves it, and attaches the
  path as `df.attrs["run_dir"]`. It still returns the same DataFrame (plus `exact_lo/hi` and `h_f1_lo/hi` interval
  columns). Nothing is saved unless `save_dir` is given.
- `print_benchmark(df, wide=False)`: the compact default shows `config, dataset, context, n_with_context, n_cases,
  exact, h_f1, d1_macro_f1, d2_macro_f1` and renders scores as `0.378 [0.30-0.46]` when interval columns exist;
  `wide=True` restores today's full column set. Fits 80 columns.
- `print_context_effect(cases)`: renders `context_effect` as a small table (delta and fixed/broken counts).

### 3. Report: `climafactskg/classifiers/cards/report.py` (new)

- `render_html(runs: Sequence[BenchmarkRun], out_path) -> Path`: one self-contained file. Sections:
  1. Header: run ids, dates, commit, and a caveat that gold labels were annotated from claim text only.
  2. Comparison table: every run x config x dataset x context, best value per column marked, intervals shown; rows with
     an `error` are flagged.
  3. Grouped bar charts for `exact_match`, `h_f1` and `d2_macro_f1`, with interval error bars where available.
  4. Context effect table (from `context_effect`) and a "cases changed by context" table (claim, gold, prediction without
     and with context, capped at 20 rows). Both are skipped when no paired data exists.
  5. Run metadata.
- Charts are inline SVG built with helper functions in the module; text labels and value annotations accompany colour so
  nothing is colour-only. Colours come from CSS custom properties with a dark-mode override, using the palette and
  validator from the `dataviz` skill (checked at implementation).
- Multiple run directories are concatenated into one report; a `run` column disambiguates identical config labels.

### 4. CLI and housekeeping

- `climafactskg eval-report RUN_DIR [RUN_DIR ...] [--out PATH]`: loads the runs, writes the HTML (default:
  `<first run dir>/report.html`), prints the path. Lazy imports, like other commands.
- `.gitignore` gets `data/eval_runs/`.
- `CLAUDE.md` documents saved runs, `eval-report`, and how to read the intervals.

## Error handling

- Unknown or incomplete run directory: `ValueError` naming the missing file or column; the CLI exits non-zero.
- A combination whose classifier raised (today's error row): saved with its `error` text and no case rows; the report
  shows it flagged instead of failing.
- `save_dir` not writable (or any `OSError` while saving): logged as a warning, the DataFrame is still returned without
  `attrs["run_dir"]`; a failed save never loses the computed results.
- Empty `cases` for a combination: intervals are `NaN`, charts omit the bar.

## Testing

Offline unit tests (no network, no API key, no models):
- `save_run`/`load_run` round trip; refusal to overwrite; missing-file and missing-column errors; atomic writes leave no
  temp files.
- `bootstrap_ci`: deterministic for a fixed seed, brackets the mean, degenerate inputs (all equal, single value, empty).
- `context_effect`: fixed/broken/unchanged counts on a hand-built cases frame, partial coverage restricted to covered
  cases, no `with` rows gives an empty frame.
- `benchmark_configs`: existing columns and rows unchanged (existing tests still pass), `save_dir` writes a loadable run,
  `df.attrs["run_dir"]` set, no directory created without `save_dir`.
- `print_benchmark`: compact columns by default, `wide=True` shows all, output width stays within 80 columns.
- `render_html`: expected section headings present, every SVG parses as XML, dark-mode CSS present, no external URLs, error
  rows flagged, single and multi-run inputs, sections skipped when there is no paired data.
- CLI: `eval-report` writes the file, non-zero exit on a bad directory.

One real render at the end from the cached v2 predictions (no paid calls).

## Out of scope

Markdown export, per-class charts, confusion heatmaps, an interactive dashboard, new metrics, changing how predictions
are made, and any plotting dependency.

## Deviations while planning

- `benchmark_configs` keeps its loop in place and captures per-case rows there instead of extracting a `_run_combo`
  helper: same result, much smaller diff to code that has tests.
- The compact terminal table shows `0.378±0.08` (value and half-width of the interval) instead of
  `0.378 [0.30-0.46]` so it fits 80 columns; the HTML report shows the full interval.
- The report is built with plain Python strings, not jinja2 (only a transitive dependency).
- Found while implementing: rich crops a too-wide compact table silently, so score columns get minimum widths, the
  Error column shows only when something failed, and padding collapses; tied best bars share one value label.
- Found in the branch review: the run suffix uses the full run id (a truncated timestamp collided for runs minutes apart);
  the compact table prints failures as lines under the table because an Error column cannot fit 80 columns; evaluations
  with `n_cases == 0` show dashes; `load_run` reads text as text (empty claims, labels like `None`/`NA`); the changed-cases
  table names the dataset and is capped per (config, dataset).
