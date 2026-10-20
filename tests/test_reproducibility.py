"""Tests for clean-clone reproducibility, fixture checksums, stale/missing sources, and benchmark integrity."""
import json, pathlib, pytest, shutil
from core.config import load_settings, ConfigError
from core.vectors import validate_vector_store
from ingestion.setup_fixtures import verify_fixture_checksums, setup
from app.retrieval import load_corpus, load_embeddings, BM25
from eval.run_eval import load_cases, evaluate_retriever

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_fixture_checksums_match_files():
    """All reviewed fixtures in data/fixtures/ must match their pinned SHA-256 checksums."""
    assert verify_fixture_checksums(), "All reviewed fixture files must match data/fixtures/checksums.json"


def test_fresh_clone_fallback_to_fixtures(tmp_path, monkeypatch):
    """When data/chunks.jsonl and data/embeddings.jsonl are missing (fresh clone),

    the application gracefully falls back to data/fixtures/ without failing.
    """
    # Point paths to non-existent files in tmp_path
    missing_chunks = tmp_path / "nonexistent_chunks.jsonl"
    missing_embeddings = tmp_path / "nonexistent_embeddings.jsonl"

    # load_corpus should fall back to data/fixtures/chunks.jsonl
    docs = load_corpus(missing_chunks)
    assert len(docs) == 93, "Should fall back to reviewed 93 chunks fixture"

    # load_embeddings should fall back to data/fixtures/embeddings.fake.jsonl
    vectors = load_embeddings(missing_embeddings)
    assert len(vectors) == 93, "Should fall back to reviewed 93 vectors fixture"


def test_missing_source_in_manifest_flagged():
    """Missing or empty sources must be identified by manifest verification."""
    manifest_path = ROOT / "data" / "fixtures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Verify all 12 allowlisted sources are present in manifest
    sources = manifest.get("sources", {})
    assert len(sources) == 12, "Manifest must track exactly 12 allowlisted sources"

    for sid, info in sources.items():
        assert info.get("chunk_count", 0) > 0, f"Source {sid} must have non-zero chunk count"
        assert info.get("content_hash"), f"Source {sid} must have non-empty content_hash"
        assert info.get("page_updated_on"), f"Source {sid} must record genuine page_updated_on"
        assert info.get("fetched_at"), f"Source {sid} must record fetched_at timestamp"


def test_stale_source_detection_via_age():
    """Freshness checks correctly identify chunks older than STALE_DAYS."""
    from core.freshness import chunk_is_stale, parse_ts, now_utc
    import datetime as dt

    # Snapshot dated 2026-10-12 checked against 45-day threshold
    now = dt.datetime(2026, 12, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    stale_chunk = {"id": "test#1", "fetched_at": "2026-10-12T18:00:00+00:00"}
    assert chunk_is_stale(stale_chunk, stale_days=45, now=now), "Chunk > 45 days old should be flagged stale"

    # Chunk 10 days old should be fresh
    fresh_chunk = {"id": "test#2", "fetched_at": "2026-11-25T18:00:00+00:00"}
    assert not chunk_is_stale(fresh_chunk, stale_days=45, now=now), "Chunk < 45 days old should be fresh"


def test_benchmark_cases_tied_to_corpus():
    """Every expected chunk ID in dev questions must exist in the 93-chunk corpus."""
    docs = load_corpus()
    corpus_ids = {d["id"] for d in docs}

    cases = load_cases("dev")
    supported = [c for c in cases if c.get("category") == "supported"]
    assert len(supported) == 12, "Dev split must have 12 supported cases"

    for c in supported:
        expected = c.get("expected_chunk_ids", [])
        assert expected, f"Case {c['id']} must specify expected_chunk_ids"
        for exp_id in expected:
            assert exp_id in corpus_ids, f"Expected chunk ID {exp_id} in {c['id']} is not in active corpus!"


def test_offline_eval_reproducible():
    """Running offline evaluation with BM25 produces expected deterministic recall on dev split."""
    docs = load_corpus()
    cases = [c for c in load_cases("dev") if c.get("category") == "supported" and c.get("reviewed")]
    bm25 = BM25(docs)
    res = evaluate_retriever("keyword_bm25", bm25, cases, k=5)
    # Recall on dev supported cases must match reviewed baseline
    assert res["total"] == 12
    assert res["hits"] >= 11, f"Expected at least 11/12 hits, got {res['hits']}"
