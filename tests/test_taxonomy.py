"""Data-integrity tests for the CARDS taxonomy.

The single source of truth consumed by both CARDSMatcher (label lookup) and
CARDSClassifier (display labels).
"""

from climafactskg.classifiers.cards.taxonomy import TAXONOMY


def test_taxonomy_ids_are_unique():
    ids = [entry["id"] for entry in TAXONOMY]
    assert len(ids) == len(set(ids)), "duplicate taxonomy ids found"


def test_taxonomy_entries_have_required_fields():
    for entry in TAXONOMY:
        assert entry.get("id"), f"entry missing id: {entry}"
        assert entry.get("url"), f"entry {entry['id']} missing url"
        assert entry.get("label"), f"entry {entry['id']} missing label"


def test_taxonomy_urls_end_with_id():
    for entry in TAXONOMY:
        assert entry["url"].endswith(f"#{entry['id']}"), f"url {entry['url']!r} does not match id {entry['id']!r}"


def test_taxonomy_uses_cards_namespace():
    # CARDS is a shared taxonomy (also used by CimpleKG), not owned by
    # ClimaFactsKG — its concepts live under their own namespace rather than
    # nested inside https://purl.net/climatesense/climafactskg/ns#.
    for entry in TAXONOMY:
        assert entry["url"].startswith("https://purl.net/climatesense/cards/ns#"), (
            f"url {entry['url']!r} is not under the CARDS namespace"
        )


def test_taxonomy_parent_ids_exist():
    """Every non-top-level code's parent (one segment shorter) must also be present."""
    ids = {entry["id"] for entry in TAXONOMY}
    for entry_id in ids:
        parts = entry_id.split("_")
        if len(parts) > 1:
            parent = "_".join(parts[:-1])
            assert parent in ids, f"{entry_id!r} has no parent entry {parent!r}"


def test_taxonomy_contains_root_zero():
    ids = {entry["id"] for entry in TAXONOMY}
    assert "0" in ids
