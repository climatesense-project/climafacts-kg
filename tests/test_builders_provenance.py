"""The classifier description: parsing the stored tag, the triples it adds, and that nothing already there changes."""

import preserve
from climafactskg.builders.cimplekg import generate_cimplekg_mappings
from climafactskg.builders.climafactskg import generate_climafactskg_base
from climafactskg.builders.provenance import add_classification_provenance, parse_classifier_tag
from climafactskg.utils import hash_string
from rdflib import RDF, SDO, Graph, Namespace, URIRef

NS = Namespace("https://purl.net/climatesense/climafactskg/ns#")
CARDS = Namespace("https://purl.net/climatesense/cards/ns#")
TRANSFORMER_TAG = "transformer:crarojasca/BinaryAugmentedCARDS,crarojasca/TaxonomyAugmentedCARDS"
LLM_TAG = "xplainnlp-nslp|openrouter/google/gemma-4-31b-it"
GATED_TAG = LLM_TAG + "+climatebert/distilroberta-base-climate-detector"


class TestParseClassifierTag:
    def test_the_transformer_tag_names_both_stages(self):
        name, models = parse_classifier_tag(TRANSFORMER_TAG)

        assert name == "CARDS labelling, two-stage transformer"
        assert models == ["crarojasca/BinaryAugmentedCARDS", "crarojasca/TaxonomyAugmentedCARDS"]

    def test_an_llm_tag_gives_the_provider_and_the_model_with_its_slashes(self):
        name, models = parse_classifier_tag(LLM_TAG)

        assert name == "CARDS labelling, preset xplainnlp-nslp via openrouter"
        assert models == ["google/gemma-4-31b-it"]

    def test_the_gate_model_is_a_second_model(self):
        _, models = parse_classifier_tag(GATED_TAG)

        assert models == ["google/gemma-4-31b-it", "climatebert/distilroberta-base-climate-detector"]

    def test_tags_that_name_no_model_give_nothing(self):
        for tag in (None, "", "xplainnlp-nslp", "transformer:only-one-model", "preset|nomodel"):
            assert parse_classifier_tag(tag) is None, tag


class TestAddClassificationProvenance:
    def test_the_action_names_its_models_and_the_reviews_it_labelled(self):
        g = Graph()
        reviews = [URIRef("http://example.org/a"), URIRef("http://example.org/b")]

        assert add_classification_provenance(g, NS, GATED_TAG, reviews) is True

        action = NS[f"classification_{hash_string(GATED_TAG)}"]
        assert (action, RDF.type, SDO.AssessAction) in g
        assert set(g.objects(action, SDO.object)) == set(reviews)
        instruments = {str(g.value(node, SDO.name)) for node in g.objects(action, SDO.instrument)}
        assert instruments == {"google/gemma-4-31b-it", "climatebert/distilroberta-base-climate-detector"}
        for node in g.objects(action, SDO.instrument):
            assert str(node).startswith(f"{NS}model_")
            assert (node, RDF.type, SDO.SoftwareApplication) in g

    def test_the_same_model_under_two_tags_is_one_node(self):
        g = Graph()

        add_classification_provenance(g, NS, LLM_TAG, [URIRef("http://example.org/a")])
        add_classification_provenance(g, NS, GATED_TAG, [URIRef("http://example.org/b")])

        assert len(list(g.subjects(RDF.type, SDO.AssessAction))) == 2
        assert len(list(g.subjects(RDF.type, SDO.SoftwareApplication))) == 2  # gemma, shared; the gate model

    def test_an_unnamed_classifier_adds_nothing(self):
        g = Graph()

        assert add_classification_provenance(g, NS, "xplainnlp-nslp", [URIRef("http://example.org/a")]) is False
        assert len(g) == 0


def _sks_entry(url, category, tag):
    entry = {
        "url": url,
        "lang": "en",
        "main_url": url,
        "languages": [],
        "climate_myth": "Some myth text",
        "title": "Some title",
        "what_the_science_says": "Some rebuttal",
        "cards_category": category,
    }
    if tag is not None:
        entry["cards_category_classifier"] = tag
    return entry


def _sks_graph(tmp_path, name, entries):
    path = str(tmp_path / f"{name}.db")
    with preserve.open(format="sqlite", filename=path) as db:
        for entry in entries:
            db[entry["url"]] = entry
    with preserve.open(format="sqlite", filename=path) as db:
        return generate_climafactskg_base(db)


class TestSksBuilderIsAdditive:
    def test_the_tagged_graph_holds_every_triple_of_the_untagged_one_and_only_adds_the_classifier(self, tmp_path):
        urls = ["http://example.org/a", "http://example.org/b"]
        plain = _sks_graph(tmp_path, "plain", [_sks_entry(u, "5_2", None) for u in urls])
        tagged = _sks_graph(tmp_path, "tagged", [_sks_entry(u, "5_2", TRANSFORMER_TAG) for u in urls])

        added = set(tagged) - set(plain)

        assert set(plain) <= set(tagged)  # nothing that was there is changed or removed
        action = NS[f"classification_{hash_string(TRANSFORMER_TAG)}"]
        assert {triple[0] for triple in added} <= {action} | {
            NS[f"model_{hash_string(m)}"]
            for m in ("crarojasca/BinaryAugmentedCARDS", "crarojasca/TaxonomyAugmentedCARDS")
        }
        assert len(list(tagged.objects(action, SDO.object))) == 2
        # the existing two-way link is untouched
        assert len(list(tagged.triples((None, SDO.about, CARDS["5_2"])))) == 2
        assert len(list(tagged.triples((CARDS["5_2"], SDO.subjectOf, None)))) == 2

    def test_a_review_with_no_category_or_no_named_classifier_gets_no_description(self, tmp_path):
        graph = _sks_graph(
            tmp_path,
            "mixed",
            [
                _sks_entry("http://example.org/none", "0", TRANSFORMER_TAG),  # not related: no link, so no action
                _sks_entry("http://example.org/bare", "5_2", "xplainnlp-nslp"),  # tag names no model
                _sks_entry("http://example.org/untagged", "5_2", None),
            ],
        )

        assert not list(graph.subjects(RDF.type, SDO.AssessAction))
        assert len(list(graph.triples((None, SDO.about, CARDS["5_2"])))) == 2


class TestCimpleKgMappings:
    def test_reviews_sharing_a_tag_share_one_action_and_untagged_ones_keep_their_link(self, tmp_path):
        path = str(tmp_path / "mappings.db")
        with preserve.open(format="sqlite", filename=path) as db:
            db["a"] = {
                "url": "http://data.cimple.eu/claim-review/a",
                "cards_category": "1_1",
                "cards_category_classifier": LLM_TAG,
            }
            db["b"] = {
                "url": "http://data.cimple.eu/claim-review/b",
                "cards_category": "2_1",
                "cards_category_classifier": LLM_TAG,
            }
            db["c"] = {"url": "http://data.cimple.eu/claim-review/c", "cards_category": "3_1"}
            db["d"] = {
                "url": "http://data.cimple.eu/claim-review/d",
                "cards_category": "0_0",
                "cards_category_classifier": LLM_TAG,
            }
        with preserve.open(format="sqlite", filename=path) as db:
            g = generate_cimplekg_mappings(db)

        action = NS[f"classification_{hash_string(LLM_TAG)}"]
        assert set(g.objects(action, SDO.object)) == {
            URIRef("http://data.cimple.eu/claim-review/a"),
            URIRef("http://data.cimple.eu/claim-review/b"),
        }
        assert len(list(g.triples((None, SDO.about, None)))) == 3  # a, b and the untagged c; d is not related
