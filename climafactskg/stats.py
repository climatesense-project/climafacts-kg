from __future__ import annotations

from collections import Counter
from pathlib import Path

import preserve
from rdflib import RDF, Graph, Namespace


def count_unique_values(db_path: str | Path, key: str) -> Counter:
    """Count unique values for a given key in a local dataset.

    Supports:
    - preserve sqlite stores (".db", ".sqlite")

    Args:
        db_path: Path to the local preserve sqlite dataset.
        key: The record attribute to count unique values for.

    Returns:
        Counter mapping unique values to counts. Records that do not contain
        the key are ignored. If the key exists with value None, None is counted.
    """
    db_path = Path(db_path)
    ext = db_path.suffix.lower()

    if ext not in {".db", ".sqlite"}:
        raise ValueError(
            f"Unsupported file extension '{ext}' for {db_path}. Only sqlite preserve stores are supported."
        )

    values = []
    with preserve.open(format="sqlite", filename=str(db_path)) as db:
        for entry in db:
            # Support both iteration styles: keys or (key, value) pairs
            if isinstance(entry, tuple) and len(entry) >= 2 and isinstance(entry[1], dict):
                rec = entry[1]
            else:
                try:
                    rec = db[entry]
                except Exception:
                    continue
            if isinstance(rec, dict) and key in rec:
                values.append(rec.get(key))
    unique_values = Counter(values)
    print(f"Unique values for '{key}': {len(unique_values)}")

    return unique_values


def count_graph_stats(graph_path: str | Path) -> dict:
    """Return basic statistics for an RDF graph file.

    Counts total triples and the number of nodes for key ClimaFactsKG types:
    ``sc:ClaimReview``, ``sc:ScholarlyArticle``.  Also counts ``sc:citation``
    and ``cito:cites`` triples.

    Args:
        graph_path: Path to an RDF file (Turtle, RDF/XML, …).

    Returns:
        Dict with keys: ``total_triples``, ``claim_reviews``,
        ``scholarly_articles``, ``sc_citations``, ``cito_cites``.
    """
    SDO = Namespace("https://schema.org/")  # noqa: N806
    CITO = Namespace("http://purl.org/spar/cito/")  # noqa: N806

    g = Graph()
    g.parse(str(graph_path))

    stats = {
        "total_triples": len(g),
        "claim_reviews": sum(1 for _ in g.triples((None, RDF.type, SDO.ClaimReview))),
        "scholarly_articles": sum(1 for _ in g.triples((None, RDF.type, SDO.ScholarlyArticle))),
        "sc_citations": sum(1 for _ in g.triples((None, SDO.citation, None))),
        "cito_cites": sum(1 for _ in g.triples((None, CITO.cites, None))),
    }
    return stats


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print("---------- ClimaFactsKG (SkepticalScience) ----------")
    sks_path = "data/skepticalscience_arguments_db.db"
    # Basic language and URL diversity
    count_unique_values(sks_path, key="lang")
    count_unique_values(sks_path, key="main_url")
    # Category distribution (includes None if present)
    cards_counts = count_unique_values(sks_path, key="cards_category")
    print(cards_counts)

    print("\n---------- SkepticalScience References ----------")
    refs_path = "data/skepticalscience_references_db.db"
    count_unique_values(refs_path, key="matchType")
    count_unique_values(refs_path, key="journal")
    count_unique_values(refs_path, key="year")

    print("\n---------- SkepticalScience Misinformers ----------")
    mis_path = "data/skepticalscience_misinformers.db"
    count_unique_values(mis_path, key="type")

    print("\n---------- CimpleKG ----------")
    # Note: mappings DB may not contain 'cards_category' in some snapshots.
    cimple_path = "data/cimplekg_mappings_db.db"
    cnt = count_unique_values(cimple_path, key="cards_category")
    if cnt:
        print(cnt)
        total_claims = sum(cnt.values()) - cnt.get("0_0", 0) - cnt.get(None, 0) - cnt.get("0", 0)
        print("Total claims (excluding '0'/'0_0' and None): {}".format(total_claims))
    else:
        print("No 'cards_category' field found in current CimpleKG mappings dataset.")

    print("\n---------- ClimaFactsKG RDF Graph ----------")
    graph_path = "data/climafacts_kg.ttl"
    graph_stats = count_graph_stats(graph_path)
    for stat_key, value in graph_stats.items():
        print(f"  {stat_key}: {value}")
