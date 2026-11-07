"""Offline tests for the LangChain agent: a scripted fake model stands in for the LLM."""
import asyncio
import json

from langchain_core.messages import AIMessage, ToolMessage

from app.services import agent_langchain


class ScriptedModel:
    """Returns the scripted replies in order and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []
        self.bound = {}

    def bind_tools(self, tools):
        self.bound["tools"] = [t.name for t in tools]
        return self

    def bind(self, **kwargs):
        self.bound.update(kwargs)
        return self

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def answer(text, ids=(), confidence=0.9):
    return AIMessage(content=json.dumps({
        "answer": text,
        "cited_chunk_ids": list(ids),
        "confidence": confidence,
        "needs_human_review": False,
    }))


def tool_call(name, args, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def run(query, model):
    return asyncio.run(agent_langchain.run_agent(query, chat_model=model))


def test_binds_both_tools_and_the_shared_response_format():
    model = ScriptedModel([answer("Which pump do you mean?")])
    run("Is the pump okay?", model)
    assert model.bound["tools"] == ["search_documents", "check_equipment_status"]
    assert model.bound["extra_body"]["response_format"]["type"] == "json_schema"


def test_tool_call_is_executed_traced_and_citable():
    model = ScriptedModel([
        tool_call("check_equipment_status", {"equipment_id": "scu-400"}),
        answer("SCU-400 is in fault with FAULT-T02.", ids=["equipment:SCU-400"]),
    ])
    res = run("What is SCU-400 doing?", model)
    assert [tc.tool for tc in res.tool_calls] == ["equipment.check_equipment_status"]
    assert '"status": "fault"' in res.tool_calls[0].result_full
    assert res.structured.cited_chunk_ids == ["equipment:SCU-400"]
    assert res.structured_meta.validated and res.structured_meta.attempts == 1
    # the tool result went back to the model as a ToolMessage tied to its call id
    last_turn = model.seen[-1]
    assert isinstance(last_turn[-1], ToolMessage) and last_turn[-1].tool_call_id == "c1"


def test_clarifying_question_calls_no_tool():
    res = run("Is the pump okay?", ScriptedModel([answer("Which pump do you mean?", confidence=0.0)]))
    assert res.tool_calls == []
    assert res.answer == "Which pump do you mean?"


def test_citation_the_model_never_saw_triggers_the_shared_retry():
    model = ScriptedModel([
        answer("Made up.", ids=["chunk-that-does-not-exist"]),
        answer("I have no tool results to cite.", ids=[]),
    ])
    res = run("Tell me something", model)
    assert res.structured_meta.validated and res.structured_meta.attempts == 2


def test_unknown_tool_is_reported_to_the_model_not_raised():
    model = ScriptedModel([
        tool_call("delete_everything", {}),
        answer("I can't do that.", confidence=0.0),
    ])
    res = run("Wipe the database", model)
    assert res.tool_calls[0].result_full == "Unknown tool: delete_everything"
    assert res.structured_meta.validated


def test_stops_after_max_tool_rounds():
    loops = [tool_call("check_equipment_status", {"equipment_id": "HX-9000"}, f"c{i}")
             for i in range(agent_langchain.MAX_TOOL_ROUNDS)]
    model = ScriptedModel(loops + [answer("HX-9000 is operational.", ids=["equipment:HX-9000"])])
    res = run("Status of HX-9000?", model)
    assert len(res.tool_calls) == agent_langchain.MAX_TOOL_ROUNDS
    assert res.structured_meta.attempts == 2  # the empty out-of-rounds reply was retried
