import functools
import logging
import os
from typing import Optional

import typer
from dotenv import load_dotenv
from typing_extensions import Annotated

load_dotenv()

# Suppress HuggingFace Hub progress bars and the unauthenticated-token advisory
# before any transformers/tokenizers code is imported.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Single place logging is configured for the whole app. Library modules
# (builders/, collectors/) only call logging.getLogger(__name__) — they used
# to each call logging.basicConfig() at import time too, which is a library
# anti-pattern (surprising for embedders, and only the first-imported module's
# call actually took effect since basicConfig no-ops once the root logger has
# handlers, making the resulting level/format order-dependent and accidental).
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False)
eval_app = typer.Typer(
    help="Benchmark and report on the CARDS classifiers (needs the `eval` extra).", no_args_is_help=True
)
app.add_typer(eval_app, name="eval")

# Top-level modules the optional `eval` extra provides; importing one without it means the extra is missing.
_EVAL_EXTRA_MODULES = ("pydantic_evals", "gepa", "gspread", "google")


def _needs_eval_extra(func):
    """Turns a missing `eval` extra into a one-line install hint instead of a traceback."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ModuleNotFoundError as exc:
            if (exc.name or "").split(".")[0] not in _EVAL_EXTRA_MODULES:
                raise
            logger.error(
                'Missing %r. Install the eval extra: pip install "climafactskg[eval]" (uv sync --extra eval)', exc.name
            )
            raise typer.Exit(code=1) from exc

    return wrapper


def _version_callback(value: bool):
    import climafactskg

    if value:
        print(climafactskg.version)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show the installed climafactskg version.",
            callback=_version_callback,
        ),
    ] = None,
):
    """🌍 ClimaFactsKG - An Interlinked Knowledge Graph of Scientific Evidence to Fight Climate Misinformation"""  # noqa: D415
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


def _exit_if_failed(failed: list[str], total: int) -> None:
    """Steps run independently, so one failure does not stop the rest, but it must not look like success either."""
    if failed:
        logger.error("%d of %d step(s) failed: %s", len(failed), total, ", ".join(failed))
        raise typer.Exit(code=1)


@app.command()
def collect():
    """Collect data for the ClimaFactsKG knowledge graph."""
    import climafactskg.collectors.cimplekg as cimplekg_collectors
    import climafactskg.collectors.climatesensekg as climatesensekg_collectors
    from climafactskg.collectors.skepticalscience import (
        fetch_arguments_urls,
        fetch_misinformers_urls,
        fetch_skstiptionary,
    )

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    steps = [
        ("skepticalscience arguments urls", lambda: fetch_arguments_urls(ignore_urls=ignore_urls)),
        ("skepticalscience misinformers urls", fetch_misinformers_urls),
        ("cimplekg claims", cimplekg_collectors.fetch_claims),
        ("climatesensekg claims", climatesensekg_collectors.fetch_claims),
        ("skepticalscience skstiptionary", fetch_skstiptionary),
    ]

    failed = []
    for name, run in steps:
        try:
            run()
        except Exception:
            logger.exception("Step %r failed; continuing with remaining steps.", name)
            failed.append(name)
    _exit_if_failed(failed, len(steps))


@app.command()
def process(
    climafactskg_db: str = typer.Option(
        "data/skepticalscience_arguments_db.db",
        help="Path to the SkepticalScience arguments database.",
    ),
    misinformers_db: str = typer.Option(
        "data/skepticalscience_misinformers.db",
        help="Path to the SkepticalScience misinformers database.",
    ),
    cimplekg_db: str = typer.Option("data/cimplekg_mappings_db.db", help="Path to the CimpleKG claims database."),
    climatesensekg_db: str = typer.Option(
        "data/climatesensekg_claims_db.db", help="Path to the ClimatesenseKG claims database."
    ),
    references_db: str = typer.Option(
        "data/skepticalscience_references_db.db",
        help="Path to the SkepticalScience references database.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-classify claims that already have a CARDS category.",
    ),
    concurrency: Optional[int] = typer.Option(
        None,
        "--concurrency",
        help="Maximum number of concurrent LLM calls during claim classification. "
        "Defaults to each classifier preset's own tuned concurrency. Only used "
        "with --classifier=llm.",
    ),
    classifier: str = typer.Option(
        "transformer",
        "--classifier",
        help="CARDS classifier engine: 'transformer' (default — matches the legacy classifier, no API cost) or 'llm'.",
    ),
    cache_path: Optional[str] = typer.Option(
        "data/cards_classification_cache.db",
        "--cache-path",
        help="Preserve SQLite cache for CARDS classification results, shared across all "
        "sources below so identical claim/argument text is classified once. Pass an "
        "empty string to disable caching.",
    ),
):
    """Process collected data and store it in the knowledge graph."""
    import preserve

    import climafactskg.collectors.cimplekg as cimplekg_collectors
    import climafactskg.collectors.climatesensekg as climatesensekg_collectors
    import climafactskg.collectors.skepticalscience as skepticalscience_collectors

    load_dotenv()

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]
    effective_cache_path = cache_path or None

    steps = [
        (
            "cimplekg",
            lambda: preserve.open(format="sqlite", filename=cimplekg_db),
            lambda db: cimplekg_collectors.process_all(
                db,
                cimplekg_collectors.fetch_claims(),
                force=force,
                concurrency=concurrency,
                classifier_engine=classifier,
                cache_path=effective_cache_path,
            ),
        ),
        (
            "climatesensekg",
            lambda: preserve.open(format="sqlite", filename=climatesensekg_db),
            lambda db: climatesensekg_collectors.process_all(
                db,
                climatesensekg_collectors.fetch_claims(),
                force=force,
                concurrency=concurrency,
                classifier_engine=classifier,
                cache_path=effective_cache_path,
            ),
        ),
        (
            "skepticalscience misinformers",
            lambda: preserve.open(format="sqlite", filename=misinformers_db),
            lambda db: skepticalscience_collectors.process_misinformers_urls(
                db,
                skepticalscience_collectors.fetch_misinformers_urls(ignore_urls=ignore_urls),
            ),
        ),
        (
            "skepticalscience arguments",
            lambda: preserve.open(format="sqlite", filename=climafactskg_db),
            lambda db: skepticalscience_collectors.process_all(
                db=db,
                urls=skepticalscience_collectors.fetch_arguments_urls(ignore_urls=ignore_urls),
                ignore_urls=ignore_urls,
                force=force,
                concurrency=concurrency,
                classifier_engine=classifier,
                cache_path=effective_cache_path,
            ),
        ),
        (
            "skepticalscience skstiptionary",
            lambda: preserve.open(format="sqlite", filename=references_db),
            lambda db: skepticalscience_collectors.process_skstiptionary(db),
        ),
    ]

    failed = []
    for name, open_db, run in steps:
        try:
            with open_db() as db:
                run(db)
        except Exception:
            logger.exception("Step %r failed; continuing with remaining steps.", name)
            failed.append(name)
    _exit_if_failed(failed, len(steps))


@app.command()
def build(
    climafactskg_db: str = typer.Option(
        "data/skepticalscience_arguments_db.db",
        help="Path to the SkepticalScience arguments database.",
    ),
    cards_ttl: str = typer.Option("data/cards.ttl", help="Path to the CARDS TTL file."),
    cimplekg_db: str = typer.Option("data/cimplekg_mappings_db.db", help="Path to the CimpleKG claims database."),
    climatesensekg_db: str = typer.Option(
        "data/climatesensekg_claims_db.db", help="Path to the ClimatesenseKG claims database."
    ),
    references_db: str = typer.Option(
        "data/skepticalscience_references_db.db",
        help="Path to the SkepticalScience references database.",
    ),
    output: str = typer.Option(
        "data/climafacts_kg.ttl",
        help="Path to the output file for the ClimaFactsKG knowledge graph.",
    ),
    output_format: str = typer.Option("ttl", help="Format of the output file."),
):
    """Build the ClimaFactsKG knowledge graph."""
    import os

    import preserve
    from rdflib import Namespace

    from climafactskg.builders.climafactskg import build_climafactskg
    from climafactskg.builders.sksreferenceskg import (
        generate_citations_graph,
        generate_references_graph,
    )

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    g = build_climafactskg(
        climafactskg_db=climafactskg_db,
        cards_ttl=cards_ttl,
        cimplekg_db=cimplekg_db,
        climatesensekg_db=climatesensekg_db,
        ignore_urls=ignore_urls,
    )

    if os.path.exists(references_db):
        with preserve.open(format="sqlite", filename=references_db) as ref_db:
            g += generate_references_graph(ref_db)

        with preserve.open(format="sqlite", filename=climafactskg_db) as art_db:
            with preserve.open(format="sqlite", filename=references_db) as ref_db:
                g += generate_citations_graph(art_db, ref_db)

    # Re-bind friendly prefixes that can be lost during graph merging with +=
    g.bind("bibo", Namespace("http://purl.org/ontology/bibo/"))
    g.bind("cito", Namespace("http://purl.org/spar/cito/"))
    g.bind("cards", Namespace("https://purl.net/climatesense/cards/ns#"))

    g.serialize(destination=output, format=output_format)

    # Re-parse the file we just wrote to catch build/serialization breakage
    # immediately (e.g. the multiline-Turtle-literal bug fixed previously)
    # instead of only discovering it later via a separate `validate` run.
    _validate_graph(output)


def _validate_graph(graph_path: str, min_claim_reviews: int = 1) -> None:
    """Parses *graph_path* and checks basic sanity thresholds; prints stats.

    Raises ``typer.Exit(code=1)`` if the file is not valid RDF (e.g. malformed
    Turtle syntax such as an unescaped multiline string literal), has zero
    triples, or has fewer than *min_claim_reviews* sc:ClaimReview nodes —
    each usually means a source DB was empty or missing when built.
    """
    from climafactskg.stats import count_graph_stats

    try:
        stats = count_graph_stats(graph_path)
    except Exception as e:
        logger.error("FAILED: could not parse %r as RDF: %s", graph_path, e)
        raise typer.Exit(code=1) from e

    for key, value in stats.items():
        logger.info("%s: %s", key, value)

    errors = []
    if stats["total_triples"] == 0:
        errors.append("Graph has zero triples.")
    if stats["claim_reviews"] < min_claim_reviews:
        errors.append(
            f"Graph has only {stats['claim_reviews']} sc:ClaimReview node(s), expected >= {min_claim_reviews}."
        )

    if errors:
        for error in errors:
            logger.error("FAILED: %s", error)
        raise typer.Exit(code=1)

    logger.info("OK: %r is valid (%s triples).", graph_path, stats["total_triples"])


@app.command()
def validate(
    graph_path: str = typer.Option(
        "data/climafacts_kg.ttl", help="Path to the RDF graph file to validate (Turtle, RDF/XML, ...)."
    ),
    min_claim_reviews: int = typer.Option(
        1, help="Minimum number of sc:ClaimReview nodes required for the graph to be considered valid."
    ),
):
    """Validate an RDF graph file: confirms it parses and meets basic sanity thresholds."""
    _validate_graph(graph_path, min_claim_reviews)


@app.command(name="eval-context", hidden=True)  # kept for scripts written against 2.2.0
@eval_app.command(name="context")
@_needs_eval_extra
def eval_context(
    version: str = typer.Argument(..., help="ClimateSense annotation round: 'v1' or 'v2'."),
    force: bool = typer.Option(False, "--force", help="Rebuild even if the sidecar already exists."),
):
    """Build the review-context sidecar for an evaluation dataset (needs its cached consensus CSV)."""
    from climafactskg.classifiers.cards.context import DEFAULT_CONTEXT_PATHS, build_climatesense_context

    if version not in DEFAULT_CONTEXT_PATHS:
        logger.error(
            "Unknown annotation round %r; choose one of: %s", version, ", ".join(sorted(DEFAULT_CONTEXT_PATHS))
        )
        raise typer.Exit(code=2)
    sidecar = build_climatesense_context(version, force=force)  # type: ignore[arg-type]
    logger.info("Review context for %d documents at %s", len(sidecar), DEFAULT_CONTEXT_PATHS[version])


@eval_app.command(name="run")
@_needs_eval_extra
def eval_run(
    config: Annotated[
        str, typer.Argument(help="TOML config: classifiers, datasets and run settings (eval.example.toml).")
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the plan and estimated paid calls, run nothing.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask before a run that calls paid LLM APIs.")] = False,
    report: Annotated[bool, typer.Option("--report", help="Also write report.html in the run directory.")] = False,
):
    """Benchmark the classifiers and datasets named in a config file and save the run."""
    from pathlib import Path

    from climafactskg.classifiers.cards import eval as cards_eval
    from climafactskg.classifiers.cards import runconfig

    try:
        spec, text = runconfig.load_run_config(config)
    except runconfig.ConfigError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc

    datasets = {d.label: runconfig.build_dataset(d) for d in spec.datasets}
    paid = [c for c in spec.classifiers if runconfig.is_paid(c)]
    # Paid classifiers are built (without the local ClimateBERT gate) only to consult their cache: counting hits is
    # free, no model is called and nothing local is loaded. Free classifiers are not touched until the run.
    built: dict[str, object] = {}
    for classifier_spec in paid:
        try:
            built[classifier_spec.label] = runconfig.build_classifier(classifier_spec, peek=True)
        except Exception as exc:
            logger.warning("Could not build %s to check its cache: %s", classifier_spec.label, exc)
    calls = cached = 0
    cache_checked = len(built) == len(paid)
    typer.echo(f"Classifiers: {', '.join(c.label for c in spec.classifiers)}")
    for label, dataset in datasets.items():
        total = len(dataset.cases)
        with_context = sum(1 for case in dataset.cases if getattr(case.inputs, "context", None))
        modes = [m for m in spec.run.context_modes if m == "none" or with_context]
        calls += total * len(modes) * len(paid)
        for mode in modes:
            texts = [getattr(case.inputs, "text", str(case.inputs)) for case in dataset.cases]
            contexts = [getattr(case.inputs, "context", None) if mode == "with" else None for case in dataset.cases]
            for classifier in built.values():
                counter = getattr(classifier, "count_cached", None)
                if counter is None:
                    cache_checked = False
                else:
                    cached += counter(texts, contexts if any(contexts) else None)
        typer.echo(f"Dataset {label}: {total} cases, {with_context} with context; modes: {', '.join(modes)}")
    typer.echo(f"Saving to: {spec.run.save_dir}")
    paid_names = ", ".join(c.label for c in paid) or "none"
    if not paid:
        typer.echo("Paid classifiers: none")
    elif cache_checked:
        typer.echo(
            f"Paid classifiers: {paid_names}; {calls} calls planned, {cached} already cached, {calls - cached} new"
        )
    else:
        typer.echo(f"Paid classifiers: {paid_names}; up to {calls} paid calls (cache not checked)")
    if dry_run:
        return
    if paid and not yes and not typer.confirm("Run and spend on the paid APIs?", default=False):
        raise typer.Exit(code=1)

    try:
        configs = {c.label: runconfig.build_classifier(c) for c in spec.classifiers}
    except Exception as exc:
        logger.error("Could not build the classifiers: %s", exc)
        raise typer.Exit(code=1) from exc
    df = cards_eval.benchmark_configs(
        configs,
        datasets,
        context_modes=spec.run.context_modes,
        min_context_coverage=spec.run.min_context_coverage,
        category_scores=spec.run.category_scores,
        save_dir=spec.run.save_dir,
    )
    cards_eval.print_benchmark(df)
    run_dir = df.attrs.get("run_dir")
    if run_dir:
        (Path(run_dir) / "config.toml").write_text(text, encoding="utf-8")
        if report:
            from climafactskg.classifiers.cards.report import render_html
            from climafactskg.classifiers.cards.runs import load_run

            logger.info("Wrote %s", render_html([load_run(run_dir)], str(Path(run_dir) / "report.html")))
    else:
        logger.warning("The run was not saved, so no config copy or report was written")
    # Exit non-zero after saving, so scripts and CI notice a benchmark in which a combination failed outright.
    errors = df["error"].fillna("").astype(str).str.strip() if "error" in df.columns else []
    failed = int((errors != "").sum()) if len(errors) else 0
    if failed:
        logger.error("%d of %d benchmark combination(s) failed; see the failed lines above.", failed, len(df))
        raise typer.Exit(code=1)


@app.command(name="eval-report", hidden=True)  # kept for scripts written against 2.2.0
@eval_app.command(name="report")
@_needs_eval_extra
def eval_report(
    run_dirs: Annotated[
        list[str], typer.Argument(help="One or more saved benchmark run directories (data/eval_runs/...).")
    ],
    out: Annotated[
        Optional[str], typer.Option("--out", help="Report path. Defaults to <first run dir>/report.html.")
    ] = None,
    baseline: Annotated[
        Optional[str],
        typer.Option("--baseline", help="Config to compare the others against (default: the first config)."),
    ] = None,
):
    """Render saved benchmark runs as one self-contained HTML report (tables and inline SVG charts)."""
    from climafactskg.classifiers.cards.report import render_html
    from climafactskg.classifiers.cards.runs import load_run

    try:
        runs = [load_run(path) for path in run_dirs]
    except ValueError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc
    target = out or f"{run_dirs[0].rstrip('/')}/report.html"
    try:
        logger.info("Wrote %s", render_html(runs, target, baseline=baseline))
    except ValueError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc


@app.command()
def classify(
    text: str = typer.Argument(..., help="Text to classify using CARDS."),
    classifier: str = typer.Option(
        "transformer",
        "--classifier",
        "-c",
        help="Classifier: 'transformer' (default), 'matcher', or 'llm'.",
    ),
    preset: Optional[str] = typer.Option(
        None, "--preset", "-p", help="Named LLM preset (e.g. 'climatesense-nslp'). LLM only."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="LLM provider ('openai', 'ollama', 'openrouter', 'lmstudio'). LLM only."
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model name. LLM only."),
    cache_path: Optional[str] = typer.Option(
        None, "--cache-path", help="Path to a Preserve SQLite cache file. LLM and transformer only."
    ),
    context: Optional[str] = typer.Option(
        None, "--context", help="Optional fact-check context (e.g. reviewer verdict, sources)."
    ),
    no_preclassifier: bool = typer.Option(
        False, "--no-preclassifier", help="Disable the ClimateBERT pre-classifier gate. LLM only."
    ),
    list_presets: bool = typer.Option(False, "--list-presets", help="Print all registered LLM preset names and exit."),
):
    """Classify text using the CARDS taxonomy."""
    if list_presets:
        from climafactskg.classifiers.cards import registered_presets

        for name in registered_presets():
            print(name)
        raise typer.Exit()

    if classifier == "matcher":
        from climafactskg.classifiers.cards import CARDSMatcher

        clf = CARDSMatcher()
        print(clf.classify(text, context=context))
        return

    if classifier == "llm":
        from climafactskg.classifiers.cards import CARDSLLMClassifier

        overrides = {}
        if provider is not None:
            overrides["provider"] = provider
        if model is not None:
            overrides["model"] = model
        if cache_path is not None:
            overrides["cache_path"] = cache_path

        if preset is not None:
            clf = CARDSLLMClassifier.from_preset(preset, use_preclassifier=not no_preclassifier, **overrides)
        else:
            clf = CARDSLLMClassifier(use_preclassifier=not no_preclassifier, **overrides)

        print(clf.classify(text, context=context))
        return

    from climafactskg.classifiers.cards import CARDSClassifier

    clf = CARDSClassifier(cache_path=cache_path)
    print(clf.classify(text, context=context))


@app.command()
def serve(
    rdf: str = typer.Option(
        "climafacts-kg/data/climafacts_kg.ttl",
        help="Path to the RDF file containing the knowledge graph.",
    ),
    rdf_format: str = typer.Option("ttl", help="Format of the RDF file."),
    host: str = typer.Option("127.0.0.1", help="Host to bind the SPARQL endpoint."),
    port: int = typer.Option(8000, help="Port to serve the SPARQL endpoint."),
):
    """Create a SPARQL endpoint for serving a knowledge graph."""
    from climafactskg.endpoints import climafactskg_to_sparql_endpoint, serve_endpoint

    app = climafactskg_to_sparql_endpoint(rdf, format=rdf_format)
    serve_endpoint(app, host=host, port=port)


# create a command that export the db file to json
@app.command()
def export(
    db: str = typer.Option(
        "data/skepticalscience_arguments_db.db",
        help="Path to the SkepticalScience arguments database.",
    ),
    output: str = typer.Option(
        "data/skepticalscience_arguments_db.json",
        help="Path to the output JSON file.",
    ),
):
    """Export a Preserve database to a JSON file."""
    import preserve

    from climafactskg.utils import preserve_to_json

    with preserve.open(format="sqlite", filename=db) as db_conn:
        preserve_to_json(db_conn, output)


if __name__ == "__main__":
    app()
