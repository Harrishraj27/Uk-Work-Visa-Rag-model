"""Tests for vector validation, provider separation, outages, quota errors, and semantic search."""
import json, pathlib, pytest, httpx
from core.config import ConfigError, load_settings
from core.vectors import validate_vector_store, compute_file_hash, compute_vectors_checksum
from core.llm import OpenAICompatLLM, OpenAICompatEmbedder, FakeEmbedder, build_embedder
from app.retrieval import VectorSearch, BM25, HybridRetriever

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_reject_fake_vectors_when_real_provider_configured(tmp_path):
    """When a real provider is configured, fake-labeled vectors must be rejected."""
    fake_file = tmp_path / "embeddings.jsonl"
    meta = {"_metadata": {"provider": "fake", "model": "fake-hash-embedder", "dim": 1536, "is_fake": True}}
    row = {"id": "test#1", "embedding": [0.1] * 1536}
    fake_file.write_text(json.dumps(meta) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    s = load_settings(env={
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "EMBEDDING_DIM": "1536",
        "EMBEDDING_API_KEY": "dummy",
        "EMBEDDINGS_PATH": str(fake_file),
    })

    with pytest.raises(ConfigError, match="Rejecting fake vectors"):
        validate_vector_store(s, embeddings_path=fake_file)


def test_reject_dimension_mismatch(tmp_path):
    """Vector store dimension must match settings.embedding_dim."""
    emb_file = tmp_path / "embeddings.jsonl"
    meta = {"_metadata": {"provider": "fake", "dim": 64, "is_fake": True}}
    row = {"id": "test#1", "embedding": [0.1] * 64}
    emb_file.write_text(json.dumps(meta) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    s = load_settings(env={
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_DIM": "1536",  # expects 1536 but file has 64
        "EMBEDDINGS_PATH": str(emb_file),
    })

    with pytest.raises(ConfigError, match="dimension mismatch"):
        validate_vector_store(s, embeddings_path=emb_file)


def test_reject_stale_vectors_when_corpus_changes(tmp_path):
    """Vectors must be rejected if chunks file hash does not match corpus_hash."""
    chk_file = tmp_path / "chunks.jsonl"
    chk_file.write_text(json.dumps({"id": "doc#1", "text": "current content"}) + "\n", encoding="utf-8")

    emb_file = tmp_path / "embeddings.jsonl"
    meta = {
        "_metadata": {
            "provider": "fake",
            "dim": 64,
            "corpus_hash": "deadbeef12345678",  # outdated hash
            "is_fake": True,
        }
    }
    row = {"id": "doc#1", "embedding": [0.1] * 64}
    emb_file.write_text(json.dumps(meta) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    s = load_settings(env={
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_DIM": "64",
        "CHUNKS_PATH": str(chk_file),
        "EMBEDDINGS_PATH": str(emb_file),
    })

    with pytest.raises(ConfigError, match="Stale vectors detected"):
        validate_vector_store(s, embeddings_path=emb_file, chunks_path=chk_file)


def test_reject_missing_chunk_vectors(tmp_path):
    """Rejects vector store if any corpus chunk lacks a vector."""
    chk_file = tmp_path / "chunks.jsonl"
    chk_file.write_text(
        json.dumps({"id": "doc#1", "text": "t1"}) + "\n" +
        json.dumps({"id": "doc#2", "text": "t2"}) + "\n",
        encoding="utf-8"
    )

    emb_file = tmp_path / "embeddings.jsonl"
    # Only doc#1 has a vector; doc#2 is missing
    meta = {"_metadata": {"provider": "fake", "dim": 64, "is_fake": True}}
    row = {"id": "doc#1", "embedding": [0.1] * 64}
    emb_file.write_text(json.dumps(meta) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    s = load_settings(env={
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_DIM": "64",
        "CHUNKS_PATH": str(chk_file),
        "EMBEDDINGS_PATH": str(emb_file),
    })

    with pytest.raises(ConfigError, match="Incomplete vector store"):
        validate_vector_store(s, embeddings_path=emb_file, chunks_path=chk_file)


def test_embedder_quota_error_handling():
    """Simulate HTTP 429 quota exhausted error on OpenAI embedding call."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            429,
            json={"error": {"message": "You exceeded your current quota", "type": "insufficient_quota"}},
            request=request,
        )
    )
    mock_client = httpx.Client(transport=mock_transport)
    embedder = OpenAICompatEmbedder("text-embedding-3-small", "sk-fake", "https://api.openai.com/v1", dim=1536, http=mock_client)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        embedder.embed(["test query"])
    assert exc_info.value.response.status_code == 429


def test_embedder_outage_handling():
    """Simulate HTTP 503 service outage error on OpenAI embedding call."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            json={"error": {"message": "Service Unavailable", "type": "server_error"}},
            request=request,
        )
    )
    mock_client = httpx.Client(transport=mock_transport)
    embedder = OpenAICompatEmbedder("text-embedding-3-small", "sk-fake", "https://api.openai.com/v1", dim=1536, http=mock_client)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        embedder.embed(["test query"])
    assert exc_info.value.response.status_code == 503


def test_llm_quota_error_handling():
    """Simulate HTTP 429 on LLM completion."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            429,
            json={"error": {"message": "Rate limit reached", "type": "requests"}},
            request=request,
        )
    )
    mock_client = httpx.Client(transport=mock_transport)
    llm = OpenAICompatLLM("gpt-4o-mini", "sk-fake", "https://api.openai.com/v1", http=mock_client)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        llm.complete("system", "user")
    assert exc_info.value.response.status_code == 429


def test_chat_and_embedding_provider_separation():
    """Embedding API key does NOT inherit LLM API key; providers are fully separate."""
    s = load_settings(env={
        "LLM_PROVIDER": "anthropic",
        "LLM_API_KEY": "sk-ant-testkey",
        "EMBEDDING_PROVIDER": "openai",
        # Notice: EMBEDDING_API_KEY is omitted
    })
    assert s.llm_api_key == "sk-ant-testkey"
    assert s.embedding_api_key == "", "EMBEDDING_API_KEY must not silently inherit LLM_API_KEY"

    # build_embedder must raise ConfigError for missing key
    with pytest.raises(ConfigError, match="API key are required"):
        build_embedder(s)


def test_vector_ranking_mechanics_with_hand_made_vectors():
    """Mechanics only: ranking/cosine works on hand-made vectors. This is NOT evidence that any real embedding model
    is semantic; that needs real vectors (see README, Real models)."""
    docs = [
        {"id": "doc#cos", "title": "Skilled Worker", "section_heading": "Overview", "text": "A certificate of sponsorship is an electronic record reference from your employer."},
        {"id": "doc#unrelated", "title": "Wildlife", "section_heading": "Animals", "text": "Penguins inhabit the cold southern hemisphere oceans."},
    ]

    # Query with pure synonyms: zero word overlap with 'certificate of sponsorship'
    synonym_query = "proof of authorized employment permission number"
    bm25 = BM25(docs)
    bm25_matches = bm25.search(synonym_query, k=1)
    # BM25 has no overlap with 'proof', 'authorized', 'employment', 'permission'
    assert len(bm25_matches) == 0 or bm25_matches[0]["score"] == 0.0

    # With a semantic vector mock where query vector is close to doc#cos
    vec_dim = 4
    doc_vectors = {
        "doc#cos": [0.9, 0.1, 0.0, 0.0],
        "doc#unrelated": [0.0, 0.0, 0.9, 0.1],
    }
    vs = VectorSearch(docs, embeddings=doc_vectors)
    # Query vector represents semantic alignment with employment auth
    query_vec = [0.85, 0.15, 0.0, 0.0]
    vec_results = vs.search(synonym_query, k=1, query_vec=query_vec)

    assert len(vec_results) == 1
    assert vec_results[0]["id"] == "doc#cos"
    assert vec_results[0]["score"] > 0.95


def _write_real(tmp_path, rows, **meta_over):
    chk = tmp_path / "chunks.jsonl"
    chk.write_text("".join(json.dumps({"id": r["id"], "text": "t"}) + "\n" for r in rows), encoding="utf-8")
    meta = {"provider": "openai", "model": "m", "dim": len(rows[0]["embedding"]), "corpus_hash": compute_file_hash(chk),
            "checksum": compute_vectors_checksum(rows), "count": len(rows), "is_fake": False}
    meta.update(meta_over)
    emb = tmp_path / "e.jsonl"
    emb.write_text(json.dumps({"_metadata": meta}) + "\n" + "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    s = load_settings(env={"EMBEDDING_PROVIDER": "openai", "EMBEDDING_MODEL": "m", "EMBEDDING_API_KEY": "k", "EMBEDDING_DIM": str(len(rows[0]["embedding"]))})
    return s, emb, chk


def test_valid_real_vectors_accepted(tmp_path):
    rows = [{"id": "a#1", "embedding": [0.1] * 8}, {"id": "a#2", "embedding": [0.2] * 8}]
    s, emb, chk = _write_real(tmp_path, rows)
    validate_vector_store(s, emb, chk)


def test_mixed_dimensions_rejected(tmp_path):
    rows = [{"id": "a#1", "embedding": [0.1] * 8}, {"id": "a#2", "embedding": [0.2] * 4}]
    s, emb, chk = _write_real(tmp_path, rows)
    with pytest.raises(ConfigError, match="dimension mismatch"):
        validate_vector_store(s, emb, chk)


def test_middle_float_edit_detected_by_full_checksum(tmp_path):
    good = [{"id": "a#1", "embedding": [0.1] * 20}]
    s, emb, chk = _write_real(tmp_path, good)
    tampered = [{"id": "a#1", "embedding": [0.1] * 10 + [0.9] + [0.1] * 9}]
    lines = emb.read_text().splitlines()
    emb.write_text(lines[0] + "\n" + json.dumps(tampered[0]) + "\n")
    with pytest.raises(ConfigError, match="checksum"):
        validate_vector_store(s, emb, chk)


def test_real_mode_requires_provenance_metadata(tmp_path):
    rows = [{"id": "a#1", "embedding": [0.1] * 8}]
    s, emb, chk = _write_real(tmp_path, rows)
    emb.write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(ConfigError, match="provenance"):
        validate_vector_store(s, emb, chk)


def test_wrong_model_rejected(tmp_path):
    rows = [{"id": "a#1", "embedding": [0.1] * 8}]
    s, emb, chk = _write_real(tmp_path, rows, model="other-model")
    with pytest.raises(ConfigError, match="model mismatch"):
        validate_vector_store(s, emb, chk)


def test_query_dimension_mismatch_rejected():
    docs = [{"id": "a#1", "text": "x"}]
    vs = VectorSearch(docs, embeddings={"a#1": [1.0, 0.0, 0.0, 0.0]})
    with pytest.raises(ConfigError, match="Query vector dimension"):
        vs.search("q", query_vec=[1.0, 0.0])


def test_embedder_outage_is_not_swallowed_by_vector_search():
    class Down:
        def embed(self, t):
            raise httpx.ConnectError("down")
    vs = VectorSearch([{"id": "a#1", "text": "x"}], embeddings={"a#1": [1.0, 0.0]}, embedder=Down())
    with pytest.raises(httpx.ConnectError):
        vs.search("q")


def test_embed_cli_writes_nothing_when_provider_fails(tmp_path, monkeypatch):
    import ingestion.embed as E
    (tmp_path / "c.jsonl").write_text(json.dumps({"id": "a#1", "section_heading": "h", "text": "t"}) + "\n")
    monkeypatch.setenv("CHUNKS_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("EMBEDDINGS_PATH", str(tmp_path / "out.jsonl"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "m")
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setattr(E, "get_embedder", lambda s: (_ for _ in ()).throw(RuntimeError("429 quota")))
    monkeypatch.setattr("sys.argv", ["embed", "--force"])
    with pytest.raises(SystemExit):
        E.main()
    assert not (tmp_path / "out.jsonl").exists()
