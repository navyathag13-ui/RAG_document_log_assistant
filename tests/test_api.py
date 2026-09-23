"""End-to-end API tests against the real app, real embedding model and a temporary
ChromaDB. No cloud services are configured, so /ask uses the offline fallback."""
import inspect
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_docs" / "manual.txt"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ingested(client):
    with open(SAMPLE, "rb") as f:
        r = client.post("/ingest", files={"file": ("manual.txt", f, "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_reports_offline_mode(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["llm_available"] is False
    assert body["content_safety_enabled"] is False


def test_ingest_creates_chunks(ingested):
    assert ingested["chunks_created"] > 1
    assert ingested["file_type"] == "txt"


def test_documents_lists_the_ingested_file(client, ingested):
    docs = client.get("/documents").json()
    assert docs["total_documents"] >= 1
    assert any(d["doc_id"] == ingested["doc_id"] for d in docs["documents"])


def test_search_returns_ranked_results(client, ingested):
    r = client.post("/search", json={"query": "flow rate alarm", "top_k": 3})
    assert r.status_code == 200
    results = r.json()["results"]
    assert 1 <= len(results) <= 3
    scores = [x["score"] for x in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_search_works(client, ingested):
    r = client.post("/search", json={"query": "WARN-F01", "top_k": 3, "use_hybrid": True})
    assert r.status_code == 200
    assert r.json()["retrieval_mode"] == "hybrid"


def test_ask_uses_offline_fallback_with_sources(client, ingested):
    r = client.post("/ask", json={"question": "What is the minimum flow rate?", "top_k": 2, "auto_evaluate": False})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False
    assert body["retrieval_count"] >= 1
    assert body["sources"]


def test_ask_endpoint_is_async():
    assert inspect.iscoroutinefunction(routes.ask)


def test_unsupported_file_type_is_rejected(client):
    r = client.post("/ingest", files={"file": ("bad.exe", b"data", "application/octet-stream")})
    assert r.status_code == 415


def test_deleting_unknown_document_is_404(client):
    assert client.delete("/documents/does_not_exist").status_code == 404


def test_delete_removes_document(client, ingested):
    assert client.delete(f"/documents/{ingested['doc_id']}").status_code == 200
    docs = client.get("/documents").json()
    assert all(d["doc_id"] != ingested["doc_id"] for d in docs["documents"])
