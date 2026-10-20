"""The single answer pipeline used by /ask AND by eval/run_answer_eval.py.
retrieve -> stale check -> guard -> rate/budget -> model -> secret scan -> citation gate.
No silent fallbacks: a provider failure returns evidence only, with a visible reason."""
from __future__ import annotations
import logging, re
from typing import Optional

from core.config import estimate_cost
from core.freshness import chunk_is_stale
from core.guard import check_question
from core.prompts import SYSTEM_PROMPT, build_user_prompt
from .citations import validate_citations

log = logging.getLogger(__name__)

LEAK_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIzaSy[A-Za-z0-9_\-]{33}"),
    re.compile(r"SECRET_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"export\s+[A-Z_]+="),
]

# kinds: answer | offline | refusal | abstain | retrieval_only | limited | provider_error | withheld | retrieval_error
ABSTAIN_TEXT = ("The stored sources don't contain enough to answer this. I won't guess. "
                "Check the official GOV.UK guidance or ask a regulated adviser.")


def find_secrets(text: str, extra: tuple = ()) -> list[str]:
    hits = [m for p in LEAK_PATTERNS for m in p.findall(text or "")]
    hits += [s for s in extra if s and len(s) >= 8 and s in (text or "")]
    return hits


def _provider_error_message(e: Exception, settings) -> str:
    try:
        import httpx
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code == 429:
                return "The model provider refused the request (429: quota or rate limit). No answer was generated."
            if code == 404:
                return f"The model '{settings.llm_model}' was not found (404). Check LLM_MODEL. No answer was generated."
            if code in (401, 403):
                return f"The model provider rejected the key ({code}). Check LLM_API_KEY. No answer was generated."
            return f"The model provider returned HTTP {code}. No answer was generated."
        if isinstance(e, httpx.TimeoutException):
            return "The model provider timed out. No answer was generated."
    except ImportError:
        pass
    return f"The model call failed ({type(e).__name__}). No answer was generated."


def _result(kind, question, results, answer=None, error=None, rule=None, usage=None, cost=None, report=None, raw=None):
    return {"kind": kind, "question": question, "results": results or [], "answer": answer, "error": error,
            "rule": rule, "usage": usage, "cost": cost, "citation_report": report, "raw_answer": raw}


def answer_question(question, retriever, llm, settings, budget=None, limiter=None, client_key="local", k=None) -> dict:
    question = (question or "").strip()
    k = k or settings.top_k
    snapshot_hint = ""
    guard = check_question(question, snapshot_hint)
    if guard:
        return _result("refusal", question, [], answer=guard["answer"], rule=guard["rule"])

    try:
        results = retriever.search(question, k=k)
    except Exception as e:
        log.exception("retrieval failed")
        return _result("retrieval_error", question, [], error=f"Retrieval failed ({type(e).__name__}: {e}). No fallback was used.")
    stale = {r["id"] for r in results if chunk_is_stale(r, settings.stale_days)}
    for r in results:
        r["is_stale"] = r["id"] in stale

    if llm is None:
        return _result("retrieval_only", question, results)
    if limiter is not None and not limiter.allow(client_key):
        return _result("limited", question, results, error="Rate limit reached. Please wait a moment before asking again.")
    if budget is not None and not budget.can_spend():
        return _result("limited", question, results, error="Daily usage limit reached. It resets at midnight UTC.")
    if not results:
        return _result("abstain", question, results, answer=ABSTAIN_TEXT)

    try:
        text, usage = llm.complete(SYSTEM_PROMPT, build_user_prompt(question, results, stale), max_tokens=settings.max_output_tokens)
    except Exception as e:
        log.exception("LLM call failed")
        return _result("provider_error", question, results, error=_provider_error_message(e, settings))
    if budget is not None:
        budget.add(usage)
    cost = estimate_cost(settings, usage.input_tokens, usage.output_tokens)
    cost_s = f"${cost:.4f}" if cost else None
    ud = usage.to_dict()

    text = (text or "").strip()
    if not text or "INSUFFICIENT_EVIDENCE" in text:
        return _result("abstain", question, results, answer=ABSTAIN_TEXT, usage=ud, cost=cost_s, raw=text)
    if find_secrets(text, (settings.llm_api_key, settings.embedding_api_key, settings.supabase_key)):
        return _result("withheld", question, results, error="The model output was withheld because it looked like it contained a secret.", usage=ud, cost=cost_s)

    offline = bool(getattr(llm, "is_fake", False))
    report = validate_citations(text, results)
    if not report["cited"] or report["invalid_ids"]:
        why = "cited a passage that was not retrieved" if report["invalid_ids"] else "had no citation"
        return _result("withheld", question, results, error=f"The model's answer was withheld because it {why}. The retrieved passages are shown instead.",
                       report=report, usage=ud, cost=cost_s, raw=text)
    if not offline and report["uncited_sentences"]:
        return _result("withheld", question, results, error="The model's answer was withheld because some sentences had no citation. The retrieved passages are shown instead.",
                       report=report, usage=ud, cost=cost_s, raw=text)
    return _result("offline" if offline else "answer", question, results, answer=text, report=report, usage=ud, cost=cost_s, raw=text)
