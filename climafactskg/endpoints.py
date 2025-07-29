from typing import Optional

import uvicorn
from rdflib import Dataset
from rdflib_endpoint.sparql_endpoint import SparqlEndpoint


def rdf_to_sparql_enpoint(
    file_path: str,
    format: str = "nt",
    title: str = "SPARQL endpoint",
    description: str = "A SPARQL endpoint to serve an RDF file.",
    example_query: str = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10",
    prefixes: Optional[dict] = None,
) -> SparqlEndpoint:
    """Creates and returns a SPARQL endpoint application serving RDF data from the specified file.

    Args:
        file_path (str): The path to the RDF file in N-Triples (.nt) format to be served.
        format (str): The serialization format of the RDF file (default is "nt" for N-Triples).
        title (str): The title for the SPARQL endpoint.
        description (str): The description for the SPARQL endpoint.
        example_query (str): An example SPARQL query to display.
        prefixes (dict): A dictionary of prefixes to use in the endpoint.

    Returns:
        SparqlEndpoint: A configured SPARQL endpoint application serving the RDF data.
    """
    if prefixes is None:
        prefixes = {
            "http://www.w3.org/2002/07/owl#": "owl",
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
            "http://www.w3.org/2001/XMLSchema#": "xsd",
        }

    g = Dataset()
    g.parse(file_path, format=format)

    app = SparqlEndpoint(
        graph=g,
        path="/",
        prefixes=prefixes,
        cors_enabled=True,
        title=title,
        description=description,
        example_query=example_query,
    )
    return app


def climafactskg_to_sparql_endpoint(
    file_path="climafacts/data/climafacts_kg.nt",
    format: str = "nt",
) -> SparqlEndpoint:
    """Creates and returns a SPARQL endpoint application for the ClimaFacts Knowledge Graph.

    This function sets up a SPARQL endpoint using the provided RDF data file, along with
    metadata such as a title, description, example query, and commonly used prefixes.

    Args:
        file_path (str): Path to the RDF data file in N-Triples format. Defaults to
            "climafacts/data/climafacts_kg.nt".
        format (str): The serialization format of the RDF file (default is "nt" for N-Triples).

    Returns:
        SparqlEndpoint: An application instance serving the SPARQL endpoint for the ClimaFacts Knowledge Graph.
    """
    title = "SPARQL endpoint for the ClimaFacts Knowledge Graph"
    description = "A SPARQL endpoint to serve ClimaFactsKG."
    example_query = """PREFIX sdo: <https://schema.org/>

SELECT DISTINCT ?a WHERE {
    ?a a sdo:ClaimReview.
}
"""

    prefixes = {
        "http://www.w3.org/2002/07/owl#": "owl",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
        "http://schema.org/": "sdo",
        "http://www.w3.org/2001/XMLSchema#": "xsd",
        "http://www.w3.org/2004/02/skos/core#": "skos",
        "https://purl.net/climafactskg/ns#": "cf",
    }

    return rdf_to_sparql_enpoint(
        file_path,
        title=title,
        description=description,
        example_query=example_query,
        prefixes=prefixes,
        format=format,
    )


def serve_endpoint(endpoint: SparqlEndpoint, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Starts a Uvicorn server to serve the given SPARQL endpoint.

    Args:
        endpoint (SparqlEndpoint): The SPARQL endpoint instance to serve.
        host (str, optional): The host address to bind the server to. Defaults to "0.0.0.0".
        port (int, optional): The port number to bind the server to. Defaults to 8000.

    Returns:
        None
    """
    uvicorn.run(endpoint, host=host, port=port)


if __name__ == "__main__":
    file_path = "climafacts/data/climafacts_kg.nt"
    app = climafactskg_to_sparql_endpoint(file_path)
    serve_endpoint(app, host="0.0.0.0", port=8000)
