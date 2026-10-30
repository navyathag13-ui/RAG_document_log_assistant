"""Gradio UI handlers against the real app (offline mode): each handler must
call the API, format its reply and turn API errors into readable messages."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ui import gradio_app as ui

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_docs" / "manual.txt"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ingested(client):
    return ui.ingest(client, str(SAMPLE))


def test_ingest_reports_chunks(ingested):
    assert ingested.startswith("Ingested manual.txt:")
    assert "chunks" in ingested


def test_ingest_without_file_asks_for_one(client):
    assert ui.ingest(client, None) == "Choose a file first."


def test_documents_table_lists_ingested_file(client, ingested):
    rows = ui.list_documents(client)
    assert any(row[1] == "txt" and row[2] > 1 for row in rows)


def test_ask_returns_answer_sources_and_mode(client, ingested):
    answer, sources, status = ui.ask(client, "How do I reset the system?", 3)
    assert answer
    assert 1 <= len(sources) <= 3
    assert all(len(row) == len(ui.SOURCE_HEADERS) for row in sources)
    assert "retrieval only" in status  # no LLM configured in tests


def test_ask_rejects_blank_question_without_calling_api(client):
    assert ui.ask(client, "   ", 5) == ("Type a question first.", [], "")


def test_api_validation_error_is_shown_not_raised(client):
    answer, sources, _ = ui.ask(client, "anything", 50)  # top_k above the API's limit of 20
    assert answer.startswith("Error 422")
    assert sources == []


def test_agent_without_llm_explains_instead_of_failing(client):
    answer, calls = ui.run_agent(client, "Is pump P-101 running?")
    assert answer
    assert calls == []


def test_ui_builds(client):
    demo = ui.build_ui(client)
    assert demo.title == "Engineering RAG Assistant"
