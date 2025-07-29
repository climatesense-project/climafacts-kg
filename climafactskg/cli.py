from typing import Optional

import typer
from dotenv import load_dotenv
from typing_extensions import Annotated

load_dotenv()
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
    from climafactskg.collectors.cimplekg import fetch_claims
    from climafactskg.collectors.skepticalscience import fetch_arguments_urls

    fetch_arguments_urls(
        ignore_urls=["https://skepticalscience.com/wigley-santer-2012-attribution.html"],
    )
    fetch_claims()


@app.command()
def process(
    climafactskg_db: str = typer.Option(
        "data/skepticalscience_arguments_db.json",
        help="Path to the SkepticalScience arguments database.",
    ),
    cimplekg_db: str = typer.Option("data/cimplekg_mappings_db.json", help="Path to the CimpleKG claims database."),
):
    """Process collected data and store it in the knowledge graph."""
    from tinydb import JSONStorage, TinyDB
    from tinydb_serialization import SerializationMiddleware
    from tinydb_serialization.serializers import DateTimeSerializer

    import climafactskg.collectors.cimplekg as cimplekg_collectors
    import climafactskg.collectors.skepticalscience as skepticalscience_collectors

    load_dotenv()
    serialization = SerializationMiddleware(JSONStorage)
    serialization.register_serializer(DateTimeSerializer(), "TinyDate")

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    with TinyDB(cimplekg_db, storage=serialization) as db:
        db.default_table_name = "mappings"
        cimplekg_collectors.process_all(db, cimplekg_collectors.fetch_claims())

    with TinyDB(climafactskg_db, storage=serialization) as db:
        db.default_table_name = "arguments"

        skepticalscience_collectors.process_urls(
            db=db,
            urls=skepticalscience_collectors.fetch_arguments_urls(ignore_urls=ignore_urls),
            ignore_urls=ignore_urls,
        )


@app.command()
def build(
    climafactskg_db: str = typer.Option(
        "data/skepticalscience_arguments_db.json",
        help="Path to the SkepticalScience arguments database.",
    ),
    cards_ttl: str = typer.Option("data/cards.ttl", help="Path to the CARDS TTL file."),
    cimplekg_db: str = typer.Option("data/cimplekg_mappings_db.json", help="Path to the CimpleKG claims database."),
    output: str = typer.Option(
        "data/climafacts_kg.rdf",
        help="Path to the output file for the ClimaFactsKG knowledge graph.",
    ),
    output_format: str = typer.Option("xml", help="Format of the output file."),
):
    """Build the ClimaFactsKG knowledge graph."""
    from climafactskg.builders.climafactskg import build_climafactskg

    ignore_urls = ["https://skepticalscience.com/wigley-santer-2012-attribution.html"]

    g = build_climafactskg(
        climafactskg_db=climafactskg_db,
        cards_ttl=cards_ttl,
        cimplekg_db=cimplekg_db,
        ignore_urls=ignore_urls,
    )
    g.serialize(destination=output, format=output_format)


@app.command()
def classify(text: str = typer.Argument(..., help="Text to classify using CARDS.")):
    """Classify text using CARDS."""
    from climafactskg.classifiers.cards import cards_classification

    cat = cards_classification(text)
    if cat == "0_0":
        cat = "0"
    print(cat)


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


if __name__ == "__main__":
    app()
