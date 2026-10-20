import json
from ingestion.chunk import chunk_sections, content_hash
from ingestion.fetch import extract
from app.retrieval import BM25
from app.citations import validate_citations
from core.config import load_settings, estimate_cost
from core.budget import DailyTokenBudget, RateLimiter
from core.freshness import chunk_is_stale, parse_ts, age_days
from core.llm import FakeLLM, FakeEmbedder, build_llm, Usage

DOCS = [
    {"id": "a#1", "section_heading": "Overview", "text": "A certificate of sponsorship is a reference number from your employer."},
    {"id": "a#2", "section_heading": "Extending", "text": "You cannot extend a Graduate visa."},
]


def test_chunk_ids_are_stable_and_ordered():
    ch = chunk_sections("src", [{"heading": "H", "text": "p1\n\np2"}])
    assert ch[0]["id"] == "src#1" and ch[0]["position"] == 1


def test_extract_skips_contents_and_keeps_body():
    html = """
    <html><head><meta name="govuk:updated-at" content="2026-09-09T00:00:00+00:00"></head>
    <body>
      <h1>Graduate visa</h1>
      <nav class="gem-c-contents-list"><h2>Contents</h2><ol><li>Overview</li></nav>
      <div class="gem-c-govspeak">
        <p>A Graduate visa gives you permission to stay in the UK.</p>
        <h2>Eligibility</h2>
        <p>You must be in the UK when you apply.</p>
        <h2>Related content</h2>
        <p>Tax if you come to the UK</p>
      </div>
    </body></html>
    """
    page = extract(html)
    headings = {s["heading"] for s in page["sections"]}
    assert "Contents" not in headings and "Related content" not in headings
    assert page["page_updated_on"] == "2026-09-09"
    assert any("permission to stay" in s["text"] for s in page["sections"])


def test_hash_changes_with_content():
    assert content_hash("a") != content_hash("b")


def test_bm25_finds_relevant_chunk():
    assert BM25(DOCS).search("certificate of sponsorship", 1)[0]["id"] == "a#1"


def test_bm25_returns_nothing_for_unrelated_query():
    assert BM25(DOCS).search("tuition fees in Antarctica") == []


def test_invalid_citation_is_flagged():
    v = validate_citations("It is a reference number [a#1]. Extra claim [zzz#9].", DOCS)
    assert v["invalid_ids"] == ["zzz#9"] and not v["ok"]


def test_uncited_sentence_is_flagged():
    v = validate_citations("Cited claim [a#1]. Uncited claim.", DOCS)
    assert v["uncited_sentences"] == ["Uncited claim."] and not v["ok"]


def test_valid_answer_passes():
    assert validate_citations("You cannot extend it [a#2].", DOCS)["ok"]


# ---- config tests ----

def test_load_settings_defaults():
    s = load_settings(env={})
    assert s.store == "local"
    assert s.top_k == 5
    assert s.daily_token_budget == 200_000


def test_estimate_cost_none_when_prices_unset():
    s = load_settings(env={})
    assert estimate_cost(s, 100, 50) is None


def test_estimate_cost_calculation():
    s = load_settings(env={"PRICE_IN_PER_MTOK": "3.0", "PRICE_OUT_PER_MTOK": "15.0"})
    cost = estimate_cost(s, 1_000_000, 100_000)
    assert cost == 3.0 + 1.5  # 3.0 * 1M/1M + 15.0 * 100K/1M


# ---- budget tests ----

def test_daily_budget_allows_then_blocks():
    b = DailyTokenBudget(100)
    assert b.can_spend()
    b.add(Usage(60, 50))  # 110 total
    assert not b.can_spend()


def test_rate_limiter_allows_then_blocks():
    rl = RateLimiter(2)
    assert rl.allow("user1")
    assert rl.allow("user1")
    assert not rl.allow("user1")
    assert rl.allow("user2")  # different key is fine


# ---- freshness tests ----

def test_chunk_is_stale_when_no_fetched_at():
    assert chunk_is_stale({}, stale_days=45)


def test_chunk_is_stale_when_old():
    assert chunk_is_stale({"fetched_at": "2020-01-01T00:00:00+00:00"}, stale_days=45)


def test_chunk_is_fresh_when_recent():
    from core.freshness import now_utc
    import datetime as dt
    recent = (now_utc() - dt.timedelta(days=1)).isoformat()
    assert not chunk_is_stale({"fetched_at": recent}, stale_days=45)


# ---- LLM tests ----

def test_fake_llm_returns_citation():
    llm = FakeLLM()
    text, usage = llm.complete("system", 'Question\n<evidence id="a#1" source="">\nA certificate of sponsorship is a reference number.\n</evidence>')
    assert "a#1" in text
    assert usage.input_tokens > 0


def test_fake_llm_insufficient_evidence():
    llm = FakeLLM()
    text, _ = llm.complete("system", "No evidence here")
    assert text == "INSUFFICIENT_EVIDENCE"


def test_build_llm_none_when_no_provider():
    s = load_settings(env={})
    assert build_llm(s) is None


def test_build_llm_fake():
    s = load_settings(env={"LLM_PROVIDER": "fake"})
    assert isinstance(build_llm(s), FakeLLM)


def test_fake_embedder_dimension():
    e = FakeEmbedder(dim=32)
    vecs = e.embed(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 32


# ---- retrieval tests ----

def test_vector_search_finds_relevant_chunk():
    from app.retrieval import VectorSearch
    embedder = FakeEmbedder(dim=32)
    vecs = {d["id"]: embedder.embed([d["section_heading"] + " " + d["text"]])[0] for d in DOCS}
    vs = VectorSearch(DOCS, embeddings=vecs, embedder=embedder)
    res = vs.search("certificate of sponsorship", k=1)
    assert len(res) == 1 and res[0]["id"] == "a#1"


def test_reciprocal_rank_fusion():
    from app.retrieval import reciprocal_rank_fusion
    list1 = [{"id": "a#1"}, {"id": "a#2"}]
    list2 = [{"id": "a#2"}, {"id": "a#1"}]
    fused = reciprocal_rank_fusion([list1, list2], k=60, limit=2)
    assert len(fused) == 2
    # Both items have identical RRF score: 1/61 + 1/62
    expected_score = round(1.0 / 61 + 1.0 / 62, 5)
    assert fused[0]["score"] == expected_score


def test_hybrid_retriever_combines_results():
    from app.retrieval import HybridRetriever, VectorSearch
    embedder = FakeEmbedder(dim=32)
    vecs = {d["id"]: embedder.embed([d["section_heading"] + " " + d["text"]])[0] for d in DOCS}
    vs = VectorSearch(DOCS, embeddings=vecs, embedder=embedder)
    hr = HybridRetriever(DOCS, bm25=BM25(DOCS), vector_search=vs)
    res = hr.search("certificate of sponsorship", k=1)
    assert len(res) == 1 and res[0]["id"] == "a#1"


def test_build_retriever_modes():
    from app.retrieval import build_retriever, HybridRetriever
    s_kw = load_settings(env={"RETRIEVAL_MODE": "keyword"})
    r_kw = build_retriever(s_kw, DOCS)
    assert isinstance(r_kw, BM25)

    s_hy = load_settings(env={"RETRIEVAL_MODE": "hybrid", "EMBEDDING_PROVIDER": "fake", "STORE": "local"})
    r_hy = build_retriever(s_hy, DOCS)   # uses labelled fake fixture vectors
    assert isinstance(r_hy, HybridRetriever)

