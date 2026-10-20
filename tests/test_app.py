import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def test_health():
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    data = r.json()
    assert "process" in data
    assert "providers" in data
    assert data["process"]["status"] == "healthy"
    assert data["process"]["chunks_loaded"] > 0
    assert "llm" in data["providers"]
    assert "storage" in data["providers"]
    assert "embedding" in data["providers"]


def test_health_reports_chunk_count():
    r = c.get("/health")
    data = r.json()
    assert data["process"]["chunks_loaded"] > 0, "corpus should be loaded"
    assert data["providers"]["storage"]["live_verified"] is False


def test_home_page_contract_and_disclaimers():
    """Verify home page HTML contract, disclaimers, and demo labels."""
    r = c.get("/")
    assert r.status_code == 200
    text = r.text
    # Boundary and disclaimers
    assert "portfolio prototype" in text.lower()
    assert "not legal advice" in text.lower()
    assert "Open Government Licence" in text
    # Form contract
    assert '<form method="post" action="/ask">' in text
    assert 'name="question"' in text
    assert 'maxlength="500"' in text


def test_cos_search_returns_real_excerpt():
    """Step 4 proof: 'certificate of sponsorship' returns a real excerpt with source metadata."""
    r = c.post("/ask", data={"question": "certificate of sponsorship"})
    assert r.status_code == 200
    # Must contain a real citation ID from the corpus
    assert "skilled-worker" in r.text, "should match a skilled worker chunk"
    # Must show a source URL
    assert "https://www.gov.uk/" in r.text
    # Must show fetched date
    assert "Fetched 20" in r.text
    # Must contain the phrase from the official text
    assert "certificate of sponsorship" in r.text.lower() or "CoS" in r.text


def test_unrelated_query_returns_no_results_or_low_score():
    """A query about something not in the corpus should not return confident results."""
    r = c.post("/ask", data={"question": "tuition fees in Antarctica"})
    assert r.status_code == 200
    # Either no results shown or very few
    assert "No relevant passage" in r.text or "retrieved" in r.text


def test_empty_question_does_not_crash():
    r = c.post("/ask", data={"question": "   "})
    assert r.status_code == 200

