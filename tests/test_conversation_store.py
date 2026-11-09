"""MongoDB conversation history: the store on its own, through the API, and
against a real MongoDB server when MONGODB_TEST_URI is set (CI runs one)."""
import os
import uuid
from pathlib import Path

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.db import conversation_store
from app.db.conversation_store import ConversationStore, needs_review, set_store
from app.main import app
from app.models.schemas import StructuredAnswer, StructuredMeta
from app.services import agent_service
from app.services.agent_service import AgentResult, ToolCallRecord

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_docs" / "manual.txt"
SEARCH = "DocumentSearch-search_documents"
STATUS = "EquipmentStatus-check_equipment_status"


def _mock_store() -> ConversationStore:
    return ConversationStore(mongomock.MongoClient(tz_aware=True)["test"]["turns"])


def _real_store():
    uri = os.environ.get("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("MONGODB_TEST_URI not set; real-MongoDB tests skipped")
    client = MongoClient(uri, serverSelectionTimeoutMS=2000, tz_aware=True)
    col = client["rag_test_" + uuid.uuid4().hex[:8]]["turns"]
    yield ConversationStore(col)
    client.drop_database(col.database.name)


@pytest.fixture(params=["mongomock", "mongodb"])
def store(request):
    if request.param == "mongomock":
        yield _mock_store()
    else:
        yield from _real_store()


def _turn(store, **kw):
    base = dict(endpoint="agent", session_id="s1", query="q", answer="a", llm_provider="azure_openai", latency_ms=100.0)
    base.update(kw)
    return store.record_turn(**base)


# ── the store ─────────────────────────────────────────────────────────────────

def test_disabled_store_saves_nothing_and_reads_empty():
    s = ConversationStore(None)
    assert not s.enabled
    assert _turn(s).saved is False
    assert s.session("s1") == [] and s.review_queue() == []
    assert s.stats()["review_count"] == 0


def test_turn_is_saved_with_its_trace(store):
    r = _turn(store, tool_calls=[{"tool": SEARCH, "arguments": {"query": "pump overheats", "top_k": 3}}],
              cited_chunk_ids=["c1", "c2"], grounded=True, structured_validated=True)
    assert r.saved and r.turn_id
    [doc] = store.session("s1")
    assert doc["_id"] == r.turn_id
    assert doc["tool_calls"][0]["arguments"] == {"query": "pump overheats", "top_k": 3}
    assert doc["n_tool_calls"] == 1 and doc["cited_chunk_ids"] == ["c1", "c2"]
    assert "review_reasons" not in doc
    assert doc["created_at"].tzinfo is not None


def test_session_is_returned_in_order_and_kept_apart(store):
    for q in ("first", "second", "third"):
        _turn(store, session_id="a", query=q)
    _turn(store, session_id="b", query="other")
    assert [d["query"] for d in store.session("a")] == ["first", "second", "third"]
    assert [d["query"] for d in store.session("b")] == ["other"]
    assert [d["query"] for d in store.session("a", limit=2)] == ["first", "second"]


@pytest.mark.parametrize("kw, reason", [
    ({"input_flagged": True}, "content safety flag"),
    ({"output_flagged": True}, "content safety flag"),
    ({"grounded": False}, "answer not grounded in its sources"),
    ({"structured_validated": False}, "structured output failed validation"),
    ({"model_needs_review": True}, "model asked for human review"),
])
def test_each_problem_puts_a_turn_in_the_review_queue(store, kw, reason):
    _turn(store, query="fine", grounded=True, structured_validated=True)
    _turn(store, query="problem", **kw)
    queue = store.review_queue()
    assert [d["query"] for d in queue] == ["problem"]
    assert queue[0]["review_reasons"] == [reason]


def test_unknown_groundedness_is_not_a_problem():
    assert needs_review({"grounded": None, "structured_validated": None}) == []


def test_stats_aggregate_latency_and_tool_usage(store):
    _turn(store, endpoint="ask", latency_ms=100.0)
    _turn(store, endpoint="ask", latency_ms=300.0, grounded=False)
    _turn(store, latency_ms=1000.0, tool_calls=[{"tool": SEARCH, "arguments": {}}, {"tool": STATUS, "arguments": {}}])
    _turn(store, latency_ms=2000.0, tool_calls=[{"tool": SEARCH, "arguments": {}}])
    _turn(store, latency_ms=600.0)  # clarifying question: no tools
    s = store.stats()
    by = {r["endpoint"]: r for r in s["by_endpoint"]}
    assert by["ask"] == {"endpoint": "ask", "turns": 2, "avg_latency_ms": 200.0, "max_latency_ms": 300.0,
                         "avg_tool_calls": 0.0}
    assert by["agent"]["turns"] == 3 and by["agent"]["avg_latency_ms"] == 1200.0 and by["agent"]["avg_tool_calls"] == 1.0
    assert s["tool_usage"] == [{"tool": SEARCH, "calls": 2}, {"tool": STATUS, "calls": 1}]
    assert s["review_count"] == 1


def test_unreachable_mongodb_does_not_raise():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    r = _turn(ConversationStore(dead["x"]["turns"]))
    assert r.saved is False and r.error == "ServerSelectionTimeoutError"


# ── through the API ───────────────────────────────────────────────────────────

@pytest.fixture
def api(request):
    """The real app with a mongomock store (or a real MongoDB with MONGODB_TEST_URI)."""
    backend = getattr(request, "param", "mongomock")
    gen = None
    if backend == "mongomock":
        s = _mock_store()
    else:
        gen = _real_store()
        s = next(gen)
    set_store(s)
    with TestClient(app) as client:
        with open(SAMPLE, "rb") as f:
            assert client.post("/ingest", files={"file": ("manual.txt", f, "text/plain")}).status_code == 201
        yield client
    set_store(None)
    if gen is not None:
        next(gen, None)


@pytest.fixture
def scripted_agent(monkeypatch):
    """Stand-in for the LLM agent: one search, one status check, a validated answer."""
    async def run(query):
        return AgentResult(
            query=query, answer="Check the coolant flow first.", llm_used=True, llm_provider="azure_openai",
            tool_calls=[ToolCallRecord(SEARCH, {"query": query}, "coolant flow", "check the coolant flow first"),
                        ToolCallRecord(STATUS, {"equipment_id": "P-101"}, "running", "running")],
            structured=StructuredAnswer(answer="Check the coolant flow first.", cited_chunk_ids=["c9"],
                                        confidence=0.8, needs_human_review=False),
            structured_meta=StructuredMeta(validated=True, attempts=1),
        )
    monkeypatch.setattr(agent_service, "run_agent", run)


@pytest.mark.parametrize("api", ["mongomock", "mongodb"], indirect=True)
def test_ask_and_agent_turns_build_one_session(api, scripted_agent):
    sid = "shift-" + uuid.uuid4().hex[:6]
    a = api.post("/ask", json={"question": "What is the minimum flow rate?", "top_k": 2,
                               "auto_evaluate": False, "session_id": sid})
    assert a.status_code == 200 and a.json()["turn_id"]
    b = api.post("/agent", json={"query": "Pump P-101 is overheating, what do I check?", "session_id": sid})
    assert b.status_code == 200 and b.json()["turn_id"]

    turns = api.get(f"/history/{sid}").json()
    assert [t["endpoint"] for t in turns] == ["ask", "agent"]
    assert [t["turn_id"] for t in turns] == [a.json()["turn_id"], b.json()["turn_id"]]
    assert turns[0]["llm_provider"] == "none" and len(turns[0]["cited_chunk_ids"]) == 2
    assert [c["tool"] for c in turns[1]["tool_calls"]] == [SEARCH, STATUS]
    assert turns[1]["structured_validated"] is True and turns[1]["cited_chunk_ids"] == ["c9"]

    stats = api.get("/history/stats").json()
    assert {r["endpoint"] for r in stats["by_endpoint"]} == {"ask", "agent"}
    assert {"tool": STATUS, "calls": 1} in stats["tool_usage"]


def test_unknown_session_is_404(api):
    assert api.get("/history/no-such-session").status_code == 404


def test_history_is_503_without_mongodb():
    set_store(ConversationStore(None))
    try:
        with TestClient(app) as client:
            for path in ("/history/stats", "/history/review", "/history/s1"):
                r = client.get(path)
                assert r.status_code == 503 and "MONGODB_URI" in r.json()["detail"]
            ok = client.post("/ask", json={"question": "flow rate?", "auto_evaluate": False})
            assert ok.status_code in (200, 404) and (ok.status_code == 404 or ok.json()["turn_id"] is None)
    finally:
        set_store(None)


def test_store_is_disabled_when_uri_is_unset(monkeypatch):
    monkeypatch.setattr(conversation_store.settings, "MONGODB_URI", "")
    set_store(None)
    assert conversation_store.get_store().enabled is False
    set_store(None)


def test_blocked_agent_input_is_saved_for_review(api, monkeypatch):
    from app.models.schemas import ContentSafetyResult
    from app.services import safety_service
    monkeypatch.setattr(safety_service, "check_text",
                        lambda text: ContentSafetyResult(checked=True, flagged=True, categories={"Violence": 4}))
    r = api.post("/agent", json={"query": "How do I shut down the hydraulic system?", "session_id": "blocked"})
    assert r.status_code == 400
    [turn] = api.get("/history/blocked").json()
    assert turn["input_flagged"] is True and turn["answer"] == "" and turn["review_reasons"] == ["content safety flag"]
