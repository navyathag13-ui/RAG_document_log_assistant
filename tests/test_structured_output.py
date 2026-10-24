"""Schema-validated LLM output: valid replies, invalid replies, the retry and the
fallback. The model is replaced by scripted replies so these run offline, but
they go through the real qa_service / structured_output code paths."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.schemas import ChunkResult, StructuredAnswer
from app.services import agent_service, llm_service, qa_service, structured_output

IDS = {"manual_chunk_0", "manual_chunk_1"}


def reply(**overrides):
    body = {
        "answer": "Maximum operating pressure is 280 bar.",
        "cited_chunk_ids": ["manual_chunk_0"],
        "confidence": 0.9,
        "needs_human_review": False,
    }
    body.update(overrides)
    return json.dumps(body)


def scripted(*replies):
    """A fake model call that returns the given replies in order and records feedback."""
    seen = []

    def call(feedback):
        seen.append(feedback)
        return replies[len(seen) - 1]

    return call, seen


# ── Parsing and validation ───────────────────────────────────────────────────

def test_valid_reply_parses():
    ans = structured_output.parse(reply(), IDS)
    assert ans.answer.startswith("Maximum")
    assert ans.cited_chunk_ids == ["manual_chunk_0"]
    assert ans.needs_human_review is False


@pytest.mark.parametrize(
    "raw",
    [
        "Maximum operating pressure is 280 bar.",              # not JSON
        '{"answer": "280 bar", "confidence": 0.9',               # truncated JSON
        reply(confidence=1.7),                                    # out of range
        reply(cited_chunk_ids=["made_up_chunk_9"]),               # citation not in context
        reply(answer=""),                                         # empty answer
        reply(extra_field="x"),                                   # schema forbids extras
        json.dumps({"answer": "280 bar", "confidence": 0.9}),    # missing needs_human_review
    ],
)
def test_invalid_replies_are_rejected(raw):
    with pytest.raises((ValueError, ValidationError)):
        structured_output.parse(raw, IDS)


def test_json_schema_matches_pydantic_model_fields():
    schema = structured_output.RESPONSE_FORMAT["json_schema"]
    assert schema["strict"] is True
    assert set(schema["schema"]["required"]) == set(StructuredAnswer.model_fields)


# ── Retry and fallback ───────────────────────────────────────────────────────

def test_valid_first_time_makes_one_call():
    call, seen = scripted(reply())
    ans, meta = structured_output.generate(call, IDS)
    assert meta.validated and meta.attempts == 1 and not meta.fallback_used
    assert seen == [None]


def test_invalid_then_valid_is_recovered_by_retry():
    call, seen = scripted("not json at all", reply())
    ans, meta = structured_output.generate(call, IDS)
    assert meta.validated and meta.attempts == 2
    assert ans.confidence == 0.9
    assert "failed validation" in seen[1]          # the model was told what went wrong


def test_retry_feedback_names_the_bad_citation():
    call, seen = scripted(reply(cited_chunk_ids=["ghost"]), reply())
    structured_output.generate(call, IDS)
    assert "ghost" in seen[1]


def test_invalid_twice_falls_back_and_flags_for_review():
    call, _ = scripted("garbage one", "garbage two")
    ans, meta = structured_output.generate(call, IDS)
    assert meta.fallback_used and not meta.validated and meta.attempts == 2
    assert meta.last_error
    assert ans.needs_human_review is True
    assert ans.confidence == 0.0
    assert ans.cited_chunk_ids == []
    assert ans.answer == "garbage two"


def test_async_generate_retries_and_falls_back():
    replies = iter(["{bad", reply(confidence=-1)])

    async def call(feedback):
        return next(replies)

    ans, meta = asyncio.run(structured_output.generate_async(call, IDS))
    assert meta.fallback_used and ans.needs_human_review


# ── Through qa_service with a fake chat client ───────────────────────────────

CHUNKS = [
    ChunkResult(chunk_id="manual_chunk_0", text="Maximum operating pressure: 280 bar.", score=0.8,
                doc_name="manual", file_type="txt", chunk_index=0),
    ChunkResult(chunk_id="manual_chunk_1", text="Minimum flow rate: 12 L/min.", score=0.6,
                doc_name="manual", file_type="txt", chunk_index=1),
]


class FakeClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.replies[len(self.calls) - 1]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_qa_service_requests_json_schema_and_validates(monkeypatch):
    client = FakeClient("```json\nnot valid```", reply(cited_chunk_ids=["manual_chunk_1"]))
    monkeypatch.setattr(llm_service, "get_chat_client", lambda: (client, "fake-model", "azure_openai"))

    text, used, provider, ans, meta = qa_service._llm_answer("What pressure?", CHUNKS, "system")

    assert client.calls[0]["response_format"]["type"] == "json_schema"
    assert "chunk_id: manual_chunk_0" in client.calls[0]["messages"][1]["content"]
    assert used and provider == "azure_openai"
    assert meta.validated and meta.attempts == 2
    assert text == ans.answer and ans.cited_chunk_ids == ["manual_chunk_1"]


def test_qa_service_offline_mode_still_returns_structured_view():
    text, used = qa_service._fallback_answer("What pressure?", CHUNKS)
    ans, meta = structured_output.offline(text, CHUNKS)
    assert used is False and meta.mode == "offline" and meta.attempts == 0
    assert ans.cited_chunk_ids == ["manual_chunk_0", "manual_chunk_1"]
    assert ans.needs_human_review is True


# ── Agent citations ──────────────────────────────────────────────────────────

def test_agent_citable_ids_come_from_tool_results():
    search_out = "[chunk_id: manual_chunk_3 | manual | relevance=0.71] text"
    status_out = agent_service.EquipmentStatusPlugin().check_equipment_status("hx-9000")
    trace = [
        agent_service.ToolCallRecord("documents.search_documents", {}, "", search_out),
        agent_service.ToolCallRecord("equipment.check_equipment_status", {}, "", status_out),
    ]
    assert agent_service.citable_ids(trace) == {"manual_chunk_3", "equipment:HX-9000"}
