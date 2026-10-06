"""HTTP service exposing a CARDS classifier."""

import logging
import secrets
import threading
from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_BATCH = 256
API_KEY_ENV = "CLIMAFACTSKG_API_KEY"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def build_classifier(
    classifier: str = "transformer",
    preset: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    cache_path: Optional[str] = None,
    no_preclassifier: bool = False,
):
    """Build a CARDS classifier by engine name.

    Args:
        classifier: ``"transformer"``, ``"matcher"`` or ``"llm"``.
        preset: Named LLM preset. LLM only.
        provider: LLM provider override. LLM only.
        model: LLM model override. LLM only.
        cache_path: Preserve SQLite cache file. LLM and transformer only.
        no_preclassifier: Disable the ClimateBERT gate. LLM only.

    Returns:
        An object implementing ``classify`` and ``classify_batch``.

    Raises:
        ValueError: If ``classifier`` is not a known engine.
    """
    if classifier == "matcher":
        from climafactskg.classifiers.cards import CARDSMatcher

        return CARDSMatcher()

    if classifier == "llm":
        from climafactskg.classifiers.cards import CARDSLLMClassifier

        overrides = {k: v for k, v in {"provider": provider, "model": model, "cache_path": cache_path}.items() if v}
        if preset is not None:
            return CARDSLLMClassifier.from_preset(preset, use_preclassifier=not no_preclassifier, **overrides)
        return CARDSLLMClassifier(use_preclassifier=not no_preclassifier, **overrides)

    if classifier == "transformer":
        from climafactskg.classifiers.cards import CARDSClassifier

        return CARDSClassifier(cache_path=cache_path)

    raise ValueError(f"Unknown classifier {classifier!r}; use 'transformer', 'matcher' or 'llm'.")


class ClassifyRequest(BaseModel):
    """One text to classify, with optional fact-check context."""

    text: str = Field(min_length=1)
    context: Optional[str] = None


class BatchRequest(BaseModel):
    """Texts to classify; ``contexts`` must match ``texts`` in length when given."""

    texts: list[str] = Field(min_length=1, max_length=MAX_BATCH)
    contexts: Optional[list[Optional[str]]] = None


class ClassifyResponse(BaseModel):
    """CARDS code for one text; ``None`` means the classification failed."""

    cards_category: Optional[str]


class BatchResponse(BaseModel):
    """CARDS codes in request order; ``None`` marks an item that failed."""

    cards_categories: list[Optional[str]]


def parse_api_keys(raw: Optional[str]) -> list[str]:
    """Split a comma-separated key list, dropping blanks (several keys allow rotation without downtime)."""
    return [k.strip() for k in (raw or "").split(",") if k.strip()]


def create_classifier_app(clf, name: str = "CARDS classifier", api_keys: Optional[list[str]] = None) -> FastAPI:
    """Wrap a classifier in a FastAPI app.

    Args:
        clf: Object with ``classify(text, context=None)`` and ``classify_batch(texts, contexts=None)``.
        name: Title shown in the OpenAPI docs and ``/healthz``.
        api_keys: Accepted bearer tokens for the classify routes. ``None`` or empty means no authentication.
            ``/healthz`` and the docs stay open either way.

    Returns:
        FastAPI app with ``POST /classify``, ``POST /classify/batch`` and ``GET /healthz``.
    """
    app = FastAPI(title=name)
    keys = [k.encode() for k in api_keys or []]
    bearer = HTTPBearer(auto_error=False)

    def require_key(creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)] = None) -> None:
        if not keys:
            return
        token = creds.credentials.encode() if creds else b""
        # Compare against every key so the time taken does not reveal which one matched.
        matches = [secrets.compare_digest(token, k) for k in keys]
        if not any(matches):
            raise HTTPException(
                status_code=401, detail="Invalid or missing API key", headers={"WWW-Authenticate": "Bearer"}
            )

    # Local models are not guaranteed thread-safe and the sync endpoints run in a thread pool.
    lock = threading.Lock()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "classifier": name}

    @app.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(require_key)])
    def classify(req: ClassifyRequest) -> ClassifyResponse:
        with lock:
            return ClassifyResponse(cards_category=clf.classify(req.text, context=req.context))

    @app.post("/classify/batch", response_model=BatchResponse, dependencies=[Depends(require_key)])
    def classify_batch(req: BatchRequest) -> BatchResponse:
        if req.contexts is not None and len(req.contexts) != len(req.texts):
            raise HTTPException(status_code=422, detail="contexts must have the same length as texts")
        with lock:
            return BatchResponse(cards_categories=clf.classify_batch(req.texts, contexts=req.contexts))

    return app


def serve_classifier(app: FastAPI, host: str = "127.0.0.1", port: int = 8001, authenticated: bool = False) -> None:
    """Run the classifier app with Uvicorn (binds to localhost unless told otherwise).

    Args:
        app: The app from :func:`create_classifier_app`.
        host: Address to bind.
        port: Port to bind.
        authenticated: Whether the app requires an API key; only used to warn about open network binds.
    """
    if host not in LOOPBACK_HOSTS and not authenticated:
        logger.warning("Serving on %s without authentication; set %s to require a bearer token.", host, API_KEY_ENV)
    uvicorn.run(app, host=host, port=port)
