"""Small adapters for the text model and the embedding model. No framework, no hidden defaults:
model identifiers come from settings and are recorded with every eval run."""
from __future__ import annotations
import hashlib, math, re
from dataclasses import dataclass
from typing import Callable, Optional

from .config import ConfigError, Settings


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self):
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


def _http(http):
    if http is not None:
        return http
    import httpx  # imported lazily so the pure-Python parts work without it
    return httpx.Client(timeout=60)


class OpenAICompatLLM:
    """Chat Completions-style API (OpenAI and compatible servers)."""

    def __init__(self, model, api_key, base_url, max_tokens_param="max_tokens", temperature=None, http=None):
        self.model, self.api_key, self.base_url = model, api_key, base_url.rstrip("/")
        self.max_tokens_param, self.temperature, self.http = max_tokens_param, temperature, _http(http)

    def complete(self, system: str, user: str, max_tokens: int = 400):
        body = {"model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                self.max_tokens_param: max_tokens}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        r = self.http.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=body)
        r.raise_for_status()
        data = r.json()
        text = (data["choices"][0]["message"].get("content") or "")
        u = data.get("usage") or {}
        return text, Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))


class AnthropicLLM:
    def __init__(self, model, api_key, temperature=None, http=None, base_url="https://api.anthropic.com"):
        self.model, self.api_key, self.temperature, self.http, self.base_url = model, api_key, temperature, _http(http), base_url.rstrip("/")

    def complete(self, system: str, user: str, max_tokens: int = 400):
        body = {"model": self.model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        r = self.http.post(f"{self.base_url}/v1/messages",
                           headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, json=body)
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage") or {}
        return text, Usage(u.get("input_tokens", 0), u.get("output_tokens", 0))


class OpenAICompatEmbedder:
    def __init__(self, model, api_key, base_url, dim, http=None, batch=64):
        self.model, self.api_key, self.base_url, self.dim = model, api_key, base_url.rstrip("/"), dim
        self.http, self.batch = _http(http), batch

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            part = texts[i:i + self.batch]
            r = self.http.post(f"{self.base_url}/embeddings", headers={"Authorization": f"Bearer {self.api_key}"},
                               json={"model": self.model, "input": part})
            r.raise_for_status()
            rows = sorted(r.json()["data"], key=lambda x: x["index"])
            for row in rows:
                if len(row["embedding"]) != self.dim:
                    raise ConfigError(f"Embedding dimension {len(row['embedding'])} != EMBEDDING_DIM {self.dim}. "
                                      "Use the same model and dimension for ingestion, queries and the SQL column.")
                out.append(row["embedding"])
        return out


# ---- deterministic fakes (tests, offline demo) ----
_WORD = re.compile(r"[a-z0-9]+")


class FakeEmbedder:
    model = "fake-hash-embedder"
    is_fake = True

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for w in _WORD.findall(t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


_UNUSED_STOP_WORDS = {"the", "a", "an", "of", "to", "and", "or", "is", "in", "i", "can", "do", "does", "for", "my", "it", "on", "be", "am", "are", "what", "how", "when", "where", "which", "who", "why", "you", "your", "if", "this", "that", "at", "as", "by", "with"}


OFFLINE_NOTICE = ("Offline demo mode: no language model was used, so no answer was written. "
                  "The most relevant official passage is shown below, quoted in full")


def offline_evidence_answer(question: str, chunks: list[dict]) -> str:
    """Deterministic offline stand-in. It never paraphrases or extracts sentences (that is how list headings like
    'You cannot:' get lost). It only points at the top retrieved passage, which the UI shows verbatim."""
    if not chunks:
        return "INSUFFICIENT_EVIDENCE"
    return f"{OFFLINE_NOTICE} [{chunks[0]['id']}]."


class FakeLLM:
    """Offline stand-in (is_fake = True). Points at the top evidence passage; never writes claims."""
    is_fake = True

    def __init__(self, responder: Optional[Callable[[str, str], str]] = None):
        self.responder, self.calls = responder, []

    def complete(self, system: str, user: str, max_tokens: int = 400):
        self.calls.append((system, user))
        if self.responder:
            text = self.responder(system, user)
        else:
            m_ev = re.findall(r'<evidence id="([^"]+)"[^>]*>\n(.*?)\n</evidence>', user, re.S)
            if not m_ev:
                text = "INSUFFICIENT_EVIDENCE"
            else:
                m_q = re.search(r'Question:?[ \t]*([^\r\n]*)', user, re.IGNORECASE)
                question = m_q.group(1).strip() if m_q else ""
                chunks = [{"id": cid, "text": t} for cid, t in m_ev]
                text = offline_evidence_answer(question, chunks)
        return text, Usage(len((system + user).split()), len(text.split()))


def build_llm(s: Settings, http=None):
    p = s.llm_provider
    if not p:
        return None
    if p == "fake":
        return FakeLLM()
    if not s.llm_model or not s.llm_api_key:
        raise ConfigError("LLM_MODEL and LLM_API_KEY are required when LLM_PROVIDER is set.")
    if p == "openai":
        return OpenAICompatLLM(s.llm_model, s.llm_api_key, s.llm_base_url, s.llm_max_tokens_param, s.llm_temperature, http)
    if p == "anthropic":
        return AnthropicLLM(s.llm_model, s.llm_api_key, s.llm_temperature, http)
    raise ConfigError(f"Unknown LLM_PROVIDER {p!r}")


def build_embedder(s: Settings, http=None):
    p = s.embedding_provider
    if not p:
        return None
    if p == "fake":
        return FakeEmbedder(s.embedding_dim)
    if p == "openai":
        if not s.embedding_model or not s.embedding_api_key:
            raise ConfigError("EMBEDDING_MODEL and an API key are required when EMBEDDING_PROVIDER is set.")
        return OpenAICompatEmbedder(s.embedding_model, s.embedding_api_key, s.embedding_base_url, s.embedding_dim, http)
    raise ConfigError(f"Unknown EMBEDDING_PROVIDER {p!r}")


def embedder_identity(s: Settings, embedder) -> tuple[str, int]:
    return (getattr(embedder, "model", s.embedding_model), getattr(embedder, "dim", s.embedding_dim))
