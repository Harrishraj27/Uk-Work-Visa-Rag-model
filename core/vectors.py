"""Vector validation, checksum calculation, and metadata management.

Ensures vectors match the current corpus, correct provider, model, dimension,
and prevents silent usage of fake or stale vectors in real production modes.
"""
from __future__ import annotations
import hashlib, json, pathlib
from typing import Optional, Tuple
from core.config import ConfigError, Settings

ROOT = pathlib.Path(__file__).resolve().parent.parent


def compute_file_hash(path: pathlib.Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_vectors_checksum(vectors: list[dict]) -> str:
    """Deterministic SHA-256 over every id and EVERY float of every vector (no sampling)."""
    h = hashlib.sha256()
    for row in sorted(vectors, key=lambda r: r.get("id", "")):
        emb = row.get("embedding", [])
        h.update(f"{row.get('id', '')}:{len(emb)}:".encode("utf-8"))
        h.update(",".join(f"{x:.8g}" for x in emb).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def load_embeddings_with_meta(path: pathlib.Path) -> Tuple[dict, dict[str, list[float]]]:
    """Load embeddings and optional metadata header from a jsonl file."""
    if not path.exists():
        return {}, {}

    meta = {}
    vectors = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "_metadata" in data:
                meta = data["_metadata"]
            elif "id" in data and "embedding" in data:
                vectors[data["id"]] = data["embedding"]
        except Exception:
            continue
    return meta, vectors


def validate_vector_store(
    settings: Settings,
    embeddings_path: Optional[pathlib.Path] = None,
    chunks_path: Optional[pathlib.Path] = None,
) -> Tuple[dict, dict[str, list[float]]]:
    """Strictly validates that the embeddings file matches the expected provider,

    model, dimension, and corpus hash. Rejects fake vectors if real mode is configured,
    rejects mismatched dimensions, and rejects stale vectors.
    """
    emb_path = embeddings_path or pathlib.Path(settings.embeddings_path)
    chk_path = chunks_path or pathlib.Path(settings.chunks_path)

    if not emb_path.exists():
        raise ConfigError(f"Embeddings file does not exist at {emb_path}")

    meta, vectors = load_embeddings_with_meta(emb_path)

    if not vectors:
        raise ConfigError(f"No vectors found in {emb_path}")

    # Every row must have the configured dimension (a mixed file is rejected, not sampled)
    bad = [i for i, e in vectors.items() if len(e) != settings.embedding_dim]
    if bad:
        raise ConfigError(
            f"Embedding dimension mismatch: {len(bad)} vector(s) in {emb_path.name} (first: {bad[0]}, dim {len(vectors[bad[0]])}) "
            f"do not match EMBEDDING_DIM={settings.embedding_dim}."
        )
    if any(not all(isinstance(x, (int, float)) for x in e) for e in vectors.values()):
        raise ConfigError(f"Non-numeric values found in {emb_path.name}.")

    is_fake_meta = bool(meta.get("is_fake", False)) or meta.get("provider") == "fake"
    expected_real = bool(settings.embedding_provider) and settings.embedding_provider != "fake"

    if expected_real:
        if is_fake_meta:
            raise ConfigError(f"Rejecting fake vectors: {emb_path.name} is labeled '{meta.get('provider', 'fake')}' (model={meta.get('model', 'unknown')}), but EMBEDDING_PROVIDER={settings.embedding_provider}.")
        # Real mode: metadata is mandatory so provenance can be checked.
        missing = [k for k in ("provider", "model", "dim", "corpus_hash", "checksum") if not meta.get(k)]
        if not meta or missing:
            raise ConfigError(f"Vector file {emb_path.name} has no usable provenance metadata (missing: {missing or 'all'}). Regenerate with python -m ingestion.embed --force.")
        if meta.get("provider") != settings.embedding_provider:
            raise ConfigError(f"Embedding provider mismatch: vectors from '{meta.get('provider')}', settings expect '{settings.embedding_provider}'.")
        if settings.embedding_model and meta.get("model") != settings.embedding_model:
            raise ConfigError(f"Embedding model mismatch: vectors from '{meta.get('model')}', settings expect '{settings.embedding_model}'.")
        if int(meta.get("dim", 0)) != settings.embedding_dim:
            raise ConfigError(f"Metadata dimension {meta.get('dim')} != EMBEDDING_DIM {settings.embedding_dim}.")
    if meta.get("checksum"):
        actual = compute_vectors_checksum([{"id": i, "embedding": e} for i, e in vectors.items()])
        if actual != meta["checksum"]:
            raise ConfigError(f"Vector checksum mismatch in {emb_path.name}: file was edited or corrupted. Regenerate it.")
    if meta.get("count") is not None and int(meta["count"]) != len(vectors):
        raise ConfigError(f"Vector count {len(vectors)} != metadata count {meta['count']}.")

    # Check corpus freshness / hash if chunks exist
    if chk_path.exists():
        current_corpus_hash = compute_file_hash(chk_path)
        meta_corpus_hash = meta.get("corpus_hash")
        if meta_corpus_hash and meta_corpus_hash != current_corpus_hash:
            raise ConfigError(
                f"Stale vectors detected: corpus hash in {emb_path.name} ({meta_corpus_hash[:12]}...) "
                f"does not match current {chk_path.name} ({current_corpus_hash[:12]}...). "
                f"Re-run embedding generation to update vectors."
            )

        # Check for missing vectors
        chunk_lines = [json.loads(l) for l in chk_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        missing_ids = [c["id"] for c in chunk_lines if c["id"] not in vectors]
        if missing_ids:
            raise ConfigError(
                f"Incomplete vector store: {len(missing_ids)} corpus chunks are missing from {emb_path.name} "
                f"(first missing: {missing_ids[0]})."
            )

    return meta, vectors
