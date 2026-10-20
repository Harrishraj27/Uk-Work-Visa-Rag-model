"""FastAPI application: evidence-based answers with citations, budget controls, and freshness checks."""
from __future__ import annotations
import logging, os, pathlib
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import load_settings, estimate_cost
from core.llm import build_llm, build_embedder
from core.budget import DailyTokenBudget, RateLimiter
from core.freshness import chunk_is_stale
from .pipeline import answer_question
from .retrieval import build_retriever, load_corpus

log = logging.getLogger(__name__)

BASE = pathlib.Path(__file__).resolve().parent
settings = load_settings()

app = FastAPI(title="UK Work Visa Evidence Assistant (portfolio prototype)")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# --- Startup resources (failures are recorded and shown, never silently replaced by fakes) ---
_startup_errors: dict[str, str] = {}
_docs = load_corpus()
_embedder = None
if settings.retrieval_mode == "hybrid" or settings.embedding_provider:
    try:
        _embedder = build_embedder(settings)
    except Exception as e:
        _startup_errors["embedding"] = f"{type(e).__name__}: {e}"
        log.warning("Embedder not ready: %s", e)
_retriever = None
try:
    _retriever = build_retriever(settings, _docs, _embedder)
except Exception as e:
    _startup_errors["retrieval"] = f"{type(e).__name__}: {e}"
    log.warning("Retriever not ready: %s", e)
_llm = None
try:
    _llm = build_llm(settings)
except Exception as e:
    _startup_errors["llm"] = f"{type(e).__name__}: {e}"
    log.warning("LLM not ready: %s", e)
_warnings: list[str] = []
if settings.llm_api_key and settings.llm_provider in ("", "fake"):
    _warnings.append("LLM_API_KEY is filled but LLM_PROVIDER is '%s', so NO real model is used. Set LLM_PROVIDER=openai (or anthropic) and LLM_MODEL." % (settings.llm_provider or "blank"))
if settings.embedding_api_key and settings.embedding_provider in ("", "fake"):
    _warnings.append("EMBEDDING_API_KEY is filled but EMBEDDING_PROVIDER is '%s', so no real embeddings are used. Set EMBEDDING_PROVIDER=openai and EMBEDDING_MODEL." % (settings.embedding_provider or "blank"))
if settings.embedding_provider == "openai" and settings.retrieval_mode == "keyword":
    _warnings.append("EMBEDDING_PROVIDER is set but RETRIEVAL_MODE=keyword, so vectors are not used for search. Set RETRIEVAL_MODE=hybrid after running python -m ingestion.embed --force.")
if (settings.supabase_url or settings.supabase_key) and settings.store == "local":
    _warnings.append("Supabase values are filled but STORE=local, so Supabase is not used. Set STORE=supabase to use it.")
_budget = DailyTokenBudget(settings.daily_token_budget)
_limiter = RateLimiter(settings.rate_limit_per_min)

OGL = "Contains public sector information licensed under the Open Government Licence v3.0."


def llm_mode() -> str:
    if settings.llm_provider == "fake":
        return "offline"
    if settings.llm_provider and _llm is not None:
        return "real"
    return "none"


def ctx(request: Request, **extra):
    return {
        "request": request,
        "corpus_version": settings.corpus_version or "unversioned",
        "n_chunks": len(_docs),
        "ogl": OGL,
        "has_llm": _llm is not None,
        "llm_mode": llm_mode(),
        "retrieval_mode": settings.retrieval_mode,
        "store": settings.store,
        "startup_errors": _startup_errors,
        "config_warnings": _warnings,
        **extra,
    }


@app.get("/health")
def health(response: Response):
    """Process health (is the web app up and the corpus loaded?) is separate from provider readiness
    (are the model, embedding and storage backends configured and constructed?). 'ready' never means
    'live-verified': nothing here calls a paid provider or the database."""
    process_healthy = len(_docs) > 0
    llm_configured = bool(settings.llm_provider)
    llm_ready = _llm is not None
    embedding_configured = bool(settings.embedding_provider)
    embedding_ready = _embedder is not None
    needs_embedding = settings.retrieval_mode == "hybrid"
    supabase_configured = bool(settings.supabase_url and settings.supabase_key)
    storage_ready = settings.store == "local" or supabase_configured
    retrieval_ready = _retriever is not None
    providers_ready = (
        retrieval_ready
        and (not llm_configured or llm_ready)
        and (not needs_embedding or embedding_ready)
        and storage_ready
    )
    if not process_healthy:
        response.status_code = 503
    status_str = "unhealthy" if not process_healthy else ("ok" if providers_ready else "degraded")
    return {
        "status": status_str,
        "process": {"status": "healthy" if process_healthy else "unhealthy", "chunks_loaded": len(_docs),
                    "corpus_version": settings.corpus_version or "unversioned"},
        "providers_ready": providers_ready,
        "answer_mode": llm_mode(),
        "providers": {
            "llm": {"provider": settings.llm_provider or "none", "model": settings.llm_model or "none",
                    "configured": llm_configured, "constructed": llm_ready, "offline_fake": settings.llm_provider == "fake",
                    "live_verified": False},
            "embedding": {"provider": settings.embedding_provider or "none", "model": settings.embedding_model or "none",
                          "dimension": settings.embedding_dim, "configured": embedding_configured,
                          "constructed": embedding_ready, "required": needs_embedding, "live_verified": False},
            "retrieval": {"mode": settings.retrieval_mode, "ready": retrieval_ready},
            "storage": {"backend": settings.store, "configured": storage_ready, "live_verified": False},
        },
        "startup_errors": _startup_errors,
        "config_warnings": _warnings,
        "note": "live_verified is always false here: /health makes no provider or database calls.",
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", ctx(request))


@app.post("/ask", response_class=HTMLResponse)
def ask(request: Request, question: str = Form(..., max_length=500)):
    question = question.strip()
    if not question:
        return templates.TemplateResponse(request, "index.html", ctx(request))
    if _retriever is None:
        err = "Retrieval is not available: " + _startup_errors.get("retrieval", "unknown error") + ". Fix the configuration and restart."
        return templates.TemplateResponse(request, "index.html", ctx(request, question=question, results=[], answer=None, kind="retrieval_error", error=err), status_code=503)
    client_ip = request.client.host if request.client else "unknown"
    out = answer_question(question, _retriever, _llm, settings, budget=_budget, limiter=_limiter, client_key=client_ip)
    if out["kind"] == "retrieval_only" and settings.llm_provider and _llm is None:
        out["error"] = "The language model is not available: " + _startup_errors.get("llm", "not configured") + ". Showing passages only."
    return templates.TemplateResponse(
        request, "index.html",
        ctx(request, question=question, results=out["results"], answer=out["answer"], kind=out["kind"],
            error=out["error"], citation_report=out["citation_report"], usage=out["usage"], cost=out["cost"]),
    )
