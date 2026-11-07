"""
The same agent as agent_service.py, built on LangChain instead of Semantic Kernel.

It exists to compare the two frameworks fairly, so everything except the
framework is shared: the system prompt, both tools (the same Python methods),
the JSON response format, the validate-and-retry loop and the AgentResult it
returns. bench/agent_framework_eval.py runs both on one labeled question set.

The tool loop is written out explicitly instead of hidden in a prebuilt agent:
the model is bound to the two tools with bind_tools(), each tool call it asks
for is executed and fed back as a ToolMessage, and the loop stops when the
model answers without asking for a tool. MAX_TOOL_ROUNDS matches Semantic
Kernel's default limit of 5 automatic tool-calling rounds.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app.core.logging_config import get_logger
from app.services import llm_service, structured_output
from app.services.agent_service import (
    _AGENT_SYSTEM_PROMPT,
    AgentResult,
    DocumentSearchPlugin,
    EquipmentStatusPlugin,
    ToolCallRecord,
    citable_ids,
)
from app.models.schemas import StructuredMeta

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 5

_docs = DocumentSearchPlugin()
_equipment = EquipmentStatusPlugin()


def search_documents(query: str, top_k: int = 4) -> str:
    """Search the indexed engineering documents (manuals, troubleshooting guides, logs, notes)
    for passages relevant to a query. Use this for how/why/procedure/specification
    questions answered by documentation."""
    return _docs.search_documents(query, top_k)


def check_equipment_status(equipment_id: str) -> str:
    """Look up the current status of a piece of equipment by its ID (e.g. 'HX-9000',
    'SCU-400', 'PUMP-01'): status, active fault codes, last maintenance date, operating
    hours. Use this when the question is about a specific machine's current state, not
    documentation. This is simulated/mock data, not a live feed."""
    return _equipment.check_equipment_status(equipment_id)


# Trace names match the Semantic Kernel version ("plugin.function") so the two
# traces can be compared directly.
TOOLS = {
    "search_documents": ("documents.search_documents", StructuredTool.from_function(search_documents)),
    "check_equipment_status": ("equipment.check_equipment_status", StructuredTool.from_function(check_equipment_status)),
}


# LangChain's chat models default to timeout=None and max_retries=None. In the
# first framework eval 4 of 42 LangChain turns stalled on a request that never
# returned, while Semantic Kernel (on the OpenAI SDK's defaults, which retry)
# had none. Explicit values make a stalled call fail fast and retry.
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 2


def build_chat_model(resolved: llm_service.ResolvedLLM):
    """A LangChain chat model for whichever backend llm_service resolved."""
    if resolved.provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=resolved.model,
            azure_endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            api_version=resolved.api_version,
            timeout=REQUEST_TIMEOUT_S,
            max_retries=MAX_RETRIES,
        )
    from langchain_openai import ChatOpenAI

    # OpenAI, or Bedrock through its OpenAI-compatible endpoint.
    return ChatOpenAI(
        model=resolved.model,
        api_key=resolved.api_key,
        base_url=resolved.endpoint,
        timeout=REQUEST_TIMEOUT_S,
        max_retries=MAX_RETRIES,
    )


async def run_tool_loop(model, messages: list[BaseMessage], trace: list[ToolCallRecord]) -> str:
    """Let the model call tools until it answers in plain content (or hits MAX_TOOL_ROUNDS)."""
    for _ in range(MAX_TOOL_ROUNDS):
        reply: AIMessage = await model.ainvoke(messages)
        messages.append(reply)
        if not reply.tool_calls:
            return reply.content if isinstance(reply.content, str) else json.dumps(reply.content)
        for call in reply.tool_calls:
            name, tool = TOOLS.get(call["name"], (call["name"], None))
            if tool is None:
                result = f"Unknown tool: {call['name']}"
            else:
                try:
                    result = str(tool.invoke(call["args"]))
                except Exception as exc:  # a bad argument should reach the model, not crash the turn
                    result = f"Tool error: {exc}"
            trace.append(ToolCallRecord(name, dict(call["args"]), result[:300], result))
            logger.info("Agent tool call (LangChain): %s(%s) -> %s", name, call["args"], result[:150])
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
    # Out of rounds with no final answer: return nothing, so the structured-output
    # check fails and the shared retry asks the model for its JSON answer.
    logger.warning("LangChain agent hit %d tool rounds without a final answer", MAX_TOOL_ROUNDS)
    return ""


async def run_agent(query: str, chat_model: Optional[Any] = None) -> AgentResult:
    """One agent turn on LangChain. chat_model lets tests pass a fake model."""
    resolved = llm_service.resolve()
    if chat_model is None and resolved.provider == "none":
        return AgentResult(
            query=query,
            answer="Agent orchestration needs a configured LLM backend; use POST /ask for retrieval-only mode.",
            llm_used=False,
            llm_provider="none",
            structured_meta=StructuredMeta(mode="offline", validated=False, attempts=0),
        )

    base = chat_model if chat_model is not None else build_chat_model(resolved)
    # The JSON response format goes in extra_body so it reaches the API exactly
    # as Semantic Kernel sends it. Passed as response_format, LangChain switches
    # to its parse() path, which requires strict tool schemas and would make the
    # two agents' requests differ.
    model = base.bind_tools([tool for _, tool in TOOLS.values()]).bind(
        extra_body={"response_format": structured_output.RESPONSE_FORMAT}
    )

    trace: list[ToolCallRecord] = []
    messages: list[BaseMessage] = [SystemMessage(_AGENT_SYSTEM_PROMPT), HumanMessage(query)]
    allowed: set[str] = set()

    async def call(feedback):
        if feedback:
            messages.append(HumanMessage(feedback))
        raw = await run_tool_loop(model, messages, trace)
        allowed.clear()
        allowed.update(citable_ids(trace))
        return raw

    provider = resolved.provider if chat_model is None else "test"
    try:
        structured, meta = await structured_output.generate_async(call, allowed)
        return AgentResult(
            query=query,
            answer=structured.answer,
            llm_used=True,
            llm_provider=provider,
            tool_calls=trace,
            structured=structured,
            structured_meta=meta,
        )
    except Exception as exc:
        logger.warning("LangChain agent call via %s failed: %s", provider, exc)
        return AgentResult(
            query=query,
            answer=f"The agent's LLM call failed ({provider}): {exc}",
            llm_used=False,
            llm_provider=provider,
            tool_calls=trace,
        )
