"""Generate vector embeddings for all corpus chunks in data/chunks.jsonl.

Usage: python -m ingestion.embed [--force]
Writes to data/embeddings.jsonl (and syncs to Supabase when configured).
"""
from __future__ import annotations
import argparse, json, logging, pathlib
from core.config import ConfigError, load_settings, Settings
from core.llm import build_embedder, FakeEmbedder, embedder_identity

log = logging.getLogger(__name__)
ROOT = pathlib.Path(__file__).resolve().parent.parent


from core.vectors import compute_file_hash, compute_vectors_checksum


def get_embedder(settings: Settings):
    if not settings.embedding_provider:
        raise ConfigError("EMBEDDING_PROVIDER is empty. Set it to 'openai' (real) or 'fake' (labelled offline vectors).")
    if settings.embedding_provider == "fake":
        return FakeEmbedder(dim=settings.embedding_dim)
    # Real provider configured: do NOT fall back silently to FakeEmbedder
    embedder = build_embedder(settings)
    if embedder is None:
        raise ConfigError(f"No embedder could be built for EMBEDDING_PROVIDER={settings.embedding_provider!r}")
    # Verify connectivity / credentials with a health check probe
    embedder.embed(["health check probe"])
    return embedder


def embed_chunks(chunks: list[dict], embedder) -> list[dict]:
    texts = [f"{c.get('section_heading', '')}\n{c.get('text', '')}" for c in chunks]
    vectors = embedder.embed(texts)
    return [{"id": c["id"], "embedding": v} for c, v in zip(chunks, vectors)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-embed even if output exists")
    args = ap.parse_args()

    settings = load_settings()
    chunks_path = pathlib.Path(settings.chunks_path)
    out_path = pathlib.Path(settings.embeddings_path)

    if not chunks_path.exists():
        print(f"Chunks file not found at {chunks_path}. Run python -m ingestion.build_corpus first.")
        return

    chunks = [json.loads(l) for l in chunks_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not chunks:
        print("No chunks found to embed.")
        return

    if out_path.exists() and not args.force:
        print(f"Embeddings file {out_path} already exists. Use --force to re-generate.")
        return

    try:
        embedder = get_embedder(settings)
    except Exception as exc:   # quota, auth, outage: stop, write nothing, never fall back to fake
        print(f"STOPPED: could not reach the embedding provider ({type(exc).__name__}: {exc}). No vectors were written.")
        raise SystemExit(2)
    ident = embedder_identity(settings, embedder)
    print(f"Embedding {len(chunks)} chunks using {ident[0]} (dim={ident[1]})...")

    try:
        embeddings = embed_chunks(chunks, embedder)
    except Exception as exc:
        print(f"STOPPED: embedding failed ({type(exc).__name__}: {exc}). No vectors were written.")
        raise SystemExit(2)
    if len(embeddings) != len(chunks):
        print("STOPPED: provider returned the wrong number of vectors."); raise SystemExit(2)
    corpus_hash = compute_file_hash(chunks_path)
    checksum = compute_vectors_checksum(embeddings)
    is_fake = (ident[0] == "fake-hash-embedder" or settings.embedding_provider == "fake")

    meta = {
        "_metadata": {
            "provider": settings.embedding_provider or "fake",
            "model": ident[0],
            "dim": ident[1],
            "corpus_hash": corpus_hash,
            "checksum": checksum,
            "count": len(embeddings),
            "is_fake": is_fake,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "document_input": "section_heading + newline + text",
            "query_input": "raw question text (no prefix)",
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_content = json.dumps(meta) + "\n" + "\n".join(json.dumps(r) for r in embeddings) + "\n"
    out_path.write_text(file_content, encoding="utf-8")
    print(f"Wrote {len(embeddings)} embeddings to {out_path} with checksum {checksum[:12]}")

    print("To load into Supabase (dev project only): python -m ingestion.upload_supabase")


if __name__ == "__main__":
    main()
