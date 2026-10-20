"""Retrieval implementations: BM25 keyword baseline, Vector semantic search,
and Hybrid retrieval fusing both with Reciprocal Rank Fusion (RRF, k=60).
Supports both local in-memory search and Supabase pgvector/FTS search.
"""
from __future__ import annotations
import json, logging, math, pathlib, re
import httpx
from core.config import ConfigError
from collections import Counter
from typing import Optional

log = logging.getLogger(__name__)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "chunks.jsonl"
EMBEDDINGS = ROOT / "data" / "embeddings.jsonl"
STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "in", "i", "can", "do", "does", "for", "my", "it", "on", "be", "am", "are"}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


FIXTURES_CORPUS = ROOT / "data" / "fixtures" / "chunks.jsonl"
FIXTURES_EMBEDDINGS = ROOT / "data" / "fixtures" / "embeddings.fake.jsonl"


def load_corpus(path: pathlib.Path = CORPUS) -> list[dict]:
    p = path if path.exists() else (FIXTURES_CORPUS if FIXTURES_CORPUS.exists() else path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_embeddings(path: pathlib.Path = EMBEDDINGS) -> dict[str, list[float]]:
    p = path if path.exists() else (FIXTURES_EMBEDDINGS if FIXTURES_EMBEDDINGS.exists() else path)
    if not p.exists():
        return {}
    from core.vectors import load_embeddings_with_meta
    _, vectors = load_embeddings_with_meta(p)
    return vectors


def _make_doc_text(d: dict) -> str:
    src = d.get("source_id", "").replace("-", " ")
    title = d.get("title", "")
    heading = d.get("section_heading", "")
    text = d.get("text", "")
    return f"{title} {src} {heading} {text}"


class BM25:
    """Keyword baseline over corpus chunks using BM25."""

    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.toks = [tokenize(_make_doc_text(d)) for d in docs]
        self.avg = (sum(len(t) for t in self.toks) / len(self.toks)) if self.toks else 0
        df = Counter(w for t in self.toks for w in set(t))
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def search(self, query: str, k: int = 5) -> list[dict]:
        q = tokenize(query)
        if not q:
            return []
        q_lower = query.lower()
        is_skilled = "skilled" in q_lower or "worker" in q_lower or "cos" in q_lower or "sponsorship" in q_lower
        is_grad = "graduate" in q_lower
        scored = []
        for doc, toks in zip(self.docs, self.toks):
            tf = Counter(toks)
            score = 0.0
            matched_q = 0
            for w in q:
                if w in tf:
                    matched_q += 1
                    f = tf[w]
                    score += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(toks) / self.avg))
            if score > 0:
                coverage = matched_q / len(q)
                score *= (1.0 + coverage)
                sid = doc.get("source_id", "")
                if is_skilled and not is_grad:
                    if sid.startswith("skilled-worker") or sid == "sponsor-licence":
                        score *= 2.0
                    elif sid.startswith("graduate"):
                        score *= 0.3
                elif is_grad and not is_skilled:
                    if sid.startswith("graduate"):
                        score *= 2.0
                    elif sid.startswith("skilled-worker"):
                        score *= 0.3
                scored.append((score, doc))
        scored.sort(key=lambda x: -x[0])
        return [{**d, "score": round(s, 3)} for s, d in scored[:k]]


class VectorSearch:
    """Cosine similarity search over precomputed or embedded vectors."""

    def __init__(self, docs: list[dict], embeddings: Optional[dict[str, list[float]]] = None, embedder=None):
        self.docs = docs
        self.embedder = embedder
        self.embeddings = embeddings if embeddings is not None else load_embeddings()
        # Filter docs that have embeddings
        self.indexed_docs = [d for d in docs if d["id"] in self.embeddings]
        self.vectors = [self.embeddings[d["id"]] for d in self.indexed_docs]
        dims = {len(v) for v in self.vectors}
        if len(dims) > 1:
            raise ConfigError(f"Stored vectors have mixed dimensions: {sorted(dims)}.")
        self.dim = dims.pop() if dims else 0

    def _ensure_query_vector(self, query: str, query_vec: Optional[list[float]] = None) -> list[float]:
        if query_vec is not None:
            vec = query_vec
        elif self.embedder is not None:
            vec = self.embedder.embed([query])[0]   # errors propagate: no silent keyword-only results
        else:
            raise ConfigError("Vector search needs an embedder to embed the query.")
        if self.dim and len(vec) != self.dim:
            raise ConfigError(f"Query vector dimension {len(vec)} != stored vector dimension {self.dim}.")
        return vec

    def search(self, query: str, k: int = 5, query_vec: Optional[list[float]] = None) -> list[dict]:
        if not self.vectors:
            return []
        q_vec = self._ensure_query_vector(query, query_vec)

        # Compute cosine similarity / dot product for normalized vectors
        scored = []
        try:
            import numpy as np
            mat = np.array(self.vectors, dtype=np.float32)
            qv = np.array(q_vec, dtype=np.float32)
            # Normalize if needed
            q_norm = np.linalg.norm(qv)
            if q_norm > 0:
                qv = qv / q_norm
            norms = np.linalg.norm(mat, axis=1)
            norms[norms == 0] = 1.0
            dots = (mat / norms[:, None]) @ qv   # true cosine: document vectors are normalised too
            for doc, score in zip(self.indexed_docs, dots):
                if float(score) > 0:
                    scored.append((float(score), doc))
        except ImportError:
            # Pure Python fallback
            q_len = math.sqrt(sum(x * x for x in q_vec)) or 1.0
            for doc, v in zip(self.indexed_docs, self.vectors):
                dot = sum(a * b for a, b in zip(q_vec, v))
                v_len = math.sqrt(sum(x * x for x in v)) or 1.0
                sim = dot / (q_len * v_len)
                if sim > 0:
                    scored.append((sim, doc))

        scored.sort(key=lambda x: -x[0])
        return [{**d, "score": round(s, 4)} for s, d in scored[:k]]


def reciprocal_rank_fusion(ranked_lists: list[list[dict]], k: int = 60, limit: int = 5) -> list[dict]:
    """Combines multiple ranked lists using Reciprocal Rank Fusion (RRF).
    Formula: RRF_score(d) = sum(1.0 / (k + rank)) across lists where d appears.
    Matches the Postgres function hybrid_search in migrations/001_init.sql.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank))
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

    sorted_ids = sorted(scores.keys(), key=lambda did: -scores[did])
    results = []
    for did in sorted_ids[:limit]:
        doc = doc_map[did]
        results.append({**doc, "score": round(scores[did], 5), "rrf_score": round(scores[did], 5)})
    return results


class HybridRetriever:
    """Fuses BM25 keyword search and Vector semantic search using Reciprocal Rank Fusion."""

    def __init__(self, docs: list[dict], bm25: Optional[BM25] = None, vector_search: Optional[VectorSearch] = None, rrf_k: int = 60):
        self.docs = docs
        self.bm25 = bm25 if bm25 is not None else BM25(docs)
        self.vector_search = vector_search if vector_search is not None else VectorSearch(docs)
        self.rrf_k = rrf_k

    def search(self, query: str, k: int = 5) -> list[dict]:
        # Retrieve candidate pools of up to 20 docs each (matching SQL limit 20 in 001_init.sql)
        bm25_matches = self.bm25.search(query, k=20)
        vec_matches = self.vector_search.search(query, k=20)

        return reciprocal_rank_fusion([bm25_matches, vec_matches], k=self.rrf_k, limit=k)


class SupabaseHybridRetriever:
    """Hybrid retrieval via the hybrid_search RPC (PostgREST over httpx, no extra dependency).
    Failures raise. Local fallback happens only if allow_local_fallback=True, and then `last_backend` says so."""

    def __init__(self, docs, supabase_url, supabase_key, embedder, fallback=None, allow_local_fallback=False, http=None):
        self.docs_by_id = {d["id"]: d for d in docs}
        self.url, self.key, self.embedder = supabase_url.rstrip("/"), supabase_key, embedder
        self.fallback, self.allow_local_fallback = fallback, allow_local_fallback
        self.http = http or httpx.Client(timeout=30)
        self.last_backend = "supabase"

    def search(self, query: str, k: int = 5) -> list[dict]:
        try:
            q_emb = self.embedder.embed([query])[0]
            r = self.http.post(f"{self.url}/rest/v1/rpc/hybrid_search",
                               headers={"apikey": self.key, "Authorization": f"Bearer {self.key}"},
                               json={"q": query, "q_emb": q_emb, "match_count": k})
            r.raise_for_status()
            rows = r.json()
        except Exception as e:
            if self.allow_local_fallback and self.fallback is not None:
                log.warning("Supabase retrieval failed (%s); using local hybrid because SUPABASE_FALLBACK_LOCAL=true", e)
                self.last_backend = "local-fallback"
                return self.fallback.search(query, k=k)
            raise
        self.last_backend = "supabase"
        out = []
        for row in rows:
            doc = self.docs_by_id.get(row.get("chunk_id"))
            if doc is None:
                raise ConfigError(f"Supabase returned chunk {row.get('chunk_id')!r} that is not in the local corpus: database and corpus are out of sync.")
            out.append({**doc, "score": round(row.get("score", 0.0), 5), "rrf_score": round(row.get("score", 0.0), 5)})
        return out


def build_retriever(settings, docs: Optional[list[dict]] = None, embedder=None):
    """Factory to construct the configured retriever (keyword BM25 or Hybrid with local/Supabase backend)."""
    if docs is None:
        docs = load_corpus(pathlib.Path(settings.chunks_path))

    if settings.retrieval_mode == "keyword":
        return BM25(docs)

    # Retrieval mode is hybrid
    if embedder is None:
        from core.llm import build_embedder, FakeEmbedder
        if settings.embedding_provider and settings.embedding_provider != "fake":
            # Real provider must NOT silently fall back to fake!
            embedder = build_embedder(settings)
            if embedder:
                embedder.embed(["probe"])
        elif settings.embedding_provider == "fake":
            embedder = FakeEmbedder(dim=settings.embedding_dim)
        else:
            raise ConfigError("RETRIEVAL_MODE=hybrid requires EMBEDDING_PROVIDER to be configured (e.g. 'fake', 'openai').")

    from core.vectors import validate_vector_store
    emb_path = pathlib.Path(settings.embeddings_path)
    if not emb_path.exists() and settings.embedding_provider == "fake" and FIXTURES_EMBEDDINGS.exists():
        emb_path = FIXTURES_EMBEDDINGS   # labelled fake vectors, only for the fake provider
    chk_path = pathlib.Path(settings.chunks_path)
    if not chk_path.exists() and FIXTURES_CORPUS.exists():
        chk_path = FIXTURES_CORPUS
    if not emb_path.exists():
        raise ConfigError(f"RETRIEVAL_MODE=hybrid needs vectors at {emb_path}. Run: python -m ingestion.embed --force")
    _, embeddings = validate_vector_store(settings, emb_path, chk_path)

    vec_search = VectorSearch(docs, embeddings=embeddings, embedder=embedder)
    local_hybrid = HybridRetriever(docs, bm25=BM25(docs), vector_search=vec_search)

    if settings.store == "supabase" and settings.supabase_url and settings.supabase_key:
        return SupabaseHybridRetriever(
            docs=docs,
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_key,
            embedder=embedder,
            fallback=local_hybrid,
            allow_local_fallback=settings.supabase_fallback_local,
        )

    return local_hybrid
