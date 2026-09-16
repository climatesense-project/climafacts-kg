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

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False)


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

    fetch_arguments_urls(
        ignore_urls=["https://skepticalscience.com/wigley-santer-2012-attribution.html"],
    )
    fetch_misinformers_urls()
    cimplekg_collectors.fetch_claims()
    climatesensekg_collectors.fetch_claims()
    fetch_skstiptionary()


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
):
    """Process collected data and store it in the knowledge graph."""
    import preserve

    import climafactskg.collectors.cimplekg as cimplekg_collectors
    import climafactskg.collectors.climatesensekg as climatesensekg_collectors
    import climafactskg.collectors.skepticalscience as skepticalscience_collectors

    load_dotenv()

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

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
            ),
        ),
        (
            "skepticalscience skstiptionary",
            lambda: preserve.open(format="sqlite", filename=references_db),
            lambda db: skepticalscience_collectors.process_skstiptionary(db),
        ),
    ]

    for name, open_db, run in steps:
        try:
            with open_db() as db:
                run(db)
        except Exception:
            logger.exception("Step %r failed; continuing with remaining steps.", name)


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
        typer.echo(f"FAILED: could not parse {graph_path!r} as RDF: {e}", err=True)
        raise typer.Exit(code=1) from e

    for key, value in stats.items():
        typer.echo(f"{key}: {value}")

    errors = []
    if stats["total_triples"] == 0:
        errors.append("Graph has zero triples.")
    if stats["claim_reviews"] < min_claim_reviews:
        errors.append(
            f"Graph has only {stats['claim_reviews']} sc:ClaimReview node(s), expected >= {min_claim_reviews}."
        )

    if errors:
        for error in errors:
            typer.echo(f"FAILED: {error}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"OK: {graph_path!r} is valid ({stats['total_triples']} triples).")


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
        None, "--cache-path", help="Path to a Preserve SQLite cache file. LLM only."
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
        print(clf.classify(text))
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

        print(clf.classify(text))
        return

    from climafactskg.classifiers.cards import CARDSClassifier

    clf = CARDSClassifier()
    print(clf.classify(text))


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
