"""Describe which classifier produced the CARDS labels, from the tag stored with each classified entry.

The tag (``cards_category_classifier``) is written by ``collectors/utils.py``: ``transformer:<binary>,<taxonomy>`` for
the two-stage transformer, ``<preset>|<provider>/<model>[+<gate model>]`` for the LLM engine. Each distinct tag becomes
one ``schema:AssessAction`` whose ``schema:instrument`` values are the models that ran and whose ``schema:object``
values are the reviews it labelled. The labels themselves stay in the existing ``schema:about`` triples, so nothing
that is already in the graph changes. Entries without a tag, or with a tag that does not say which model ran (the bare
preset name older runs wrote), get no description rather than a guessed one.
"""

from collections.abc import Iterable
from typing import Optional

from rdflib import RDF, SDO, Graph, Literal, Namespace, URIRef

from climafactskg.utils import hash_string

TRANSFORMER_PREFIX = "transformer:"


def parse_classifier_tag(tag: Optional[str]) -> Optional[tuple[str, list[str]]]:
    """Read a stored classifier tag as ``(action name, model ids)``, or ``None`` when it names no model."""
    if not tag:
        return None
    if tag.startswith(TRANSFORMER_PREFIX):
        models = [model for model in tag[len(TRANSFORMER_PREFIX) :].split(",") if model]
        return ("CARDS labelling, two-stage transformer", models) if len(models) == 2 else None
    if "|" in tag:
        preset, _, rest = tag.partition("|")
        served, _, gate = rest.partition("+")
        provider, _, model = served.partition("/")
        if preset and provider and model:
            return f"CARDS labelling, preset {preset} via {provider}", [model] + ([gate] if gate else [])
    return None


def add_classification_provenance(g: Graph, ns: Namespace, tag: Optional[str], reviews: Iterable[URIRef]) -> bool:
    """Add the classifier described by *tag* and link it to the *reviews* it labelled.

    Args:
        g: Graph to add triples to.
        ns: The ClimaFactsKG instance-data namespace the new nodes are minted in.
        tag: The stored ``cards_category_classifier`` value.
        reviews: IRIs of the reviews that carry a CARDS link produced by that classifier.

    Returns:
        True if the tag named a classifier and its triples were added.
    """
    parsed = parse_classifier_tag(tag)
    if parsed is None:
        return False
    name, models = parsed
    action = ns[f"classification_{hash_string(str(tag))}"]
    g.add((action, RDF.type, SDO.AssessAction))
    g.add((action, SDO.name, Literal(name)))
    for model in models:
        node = ns[f"model_{hash_string(model)}"]
        g.add((node, RDF.type, SDO.SoftwareApplication))
        g.add((node, SDO.name, Literal(model)))
        g.add((action, SDO.instrument, node))
    for review in reviews:
        g.add((action, SDO.object, review))
    return True
