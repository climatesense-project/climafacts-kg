import pytest
from climafactskg.classifiers.cards.server import build_classifier, create_classifier_app
from fastapi.testclient import TestClient


class _Stub:
    def classify(self, text, context=None):
        return f"1_1|{context}"

    def classify_batch(self, texts, contexts=None):
        return [None if t == "bad" else "2_1" for t in texts]


@pytest.fixture
def client():
    return TestClient(create_classifier_app(_Stub(), name="stub"))


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok", "classifier": "stub"}


def test_classify_passes_context(client):
    r = client.post("/classify", json={"text": "x", "context": "ctx"})
    assert r.status_code == 200
    assert r.json() == {"cards_category": "1_1|ctx"}


def test_classify_rejects_empty_text(client):
    assert client.post("/classify", json={"text": ""}).status_code == 422


def test_batch_keeps_order_and_failures(client):
    r = client.post("/classify/batch", json={"texts": ["a", "bad"]})
    assert r.json() == {"cards_categories": ["2_1", None]}


def test_batch_context_length_mismatch(client):
    r = client.post("/classify/batch", json={"texts": ["a", "b"], "contexts": ["c"]})
    assert r.status_code == 422


def test_build_classifier_unknown_engine():
    with pytest.raises(ValueError, match="Unknown classifier"):
        build_classifier("nope")


def test_serve_commands(monkeypatch):
    from climafactskg import cli
    from typer.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli, "_serve_sparql", lambda *a: calls.append(a))
    runner = CliRunner()
    assert runner.invoke(cli.app, ["serve", "--rdf", "a.ttl", "--port", "9"]).exit_code == 0
    assert runner.invoke(cli.app, ["serve", "sparql", "--rdf", "b.ttl"]).exit_code == 0
    assert [c[0] for c in calls] == ["a.ttl", "b.ttl"]
    assert calls[0][3] == 9
    out = runner.invoke(cli.app, ["serve", "classifier", "--help"])
    assert out.exit_code == 0 and "--classifier" in out.output


class TestApiKey:
    def _client(self, keys):
        return TestClient(create_classifier_app(_Stub(), api_keys=keys))

    def test_no_keys_means_open(self):
        assert self._client(None).post("/classify", json={"text": "x"}).status_code == 200

    def test_missing_and_wrong_key_rejected(self):
        c = self._client(["k1"])
        r = c.post("/classify", json={"text": "x"})
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
        assert c.post("/classify", json={"text": "x"}, headers={"Authorization": "Bearer nope"}).status_code == 401
        assert c.post("/classify/batch", json={"texts": ["a"]}).status_code == 401

    def test_any_listed_key_accepted(self):
        c = self._client(["k1", "k2"])
        for k in ("k1", "k2"):
            r = c.post("/classify/batch", json={"texts": ["a"]}, headers={"Authorization": f"Bearer {k}"})
            assert r.status_code == 200

    def test_healthz_stays_open(self):
        assert self._client(["k1"]).get("/healthz").status_code == 200

    def test_parse_api_keys(self):
        from climafactskg.classifiers.cards.server import parse_api_keys

        assert parse_api_keys(" a, ,b ,") == ["a", "b"]
        assert parse_api_keys(None) == []
