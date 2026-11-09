"""
Agent orchestration API route (v3).

POST /agent — runs one turn of the Semantic Kernel agent (app/services/agent_service.py):
  the configured LLM decides whether to search documents, check mock equipment
  status, ask a clarifying question, or some combination, then the response is
  screened by Content Safety (input and output) and checked for groundedness
  before being returned (app/services/safety_service.py).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.db.conversation_store import Timer, get_store

from app.core.logging_config import get_logger
from app.models.schemas import AgentQuery, AgentResponse, AgentToolCall
from app.services import agent_service, safety_service

agent_router = APIRouter(tags=["Agent"])
logger = get_logger(__name__)


@agent_router.post("/agent", response_model=AgentResponse)
async def run_agent(body: AgentQuery):
    """
    Run the agent on a natural-language query.

    The agent has two tools (search_documents, check_equipment_status) and
    decides on its own, per query, whether to call one, both, or neither —
    asking a clarifying question instead when the query is ambiguous. See
    app/services/agent_service.py for the full design rationale.

    Requires a configured LLM backend (Azure OpenAI or OpenAI); without one,
    this returns a clearly labeled message rather than faking a decision —
    see GET /health for whether one is configured.
    """
    input_safety = safety_service.check_text(body.query)
    if input_safety.flagged:
        # Blocked inputs are saved too: a reviewer needs to see what was refused,
        # including false positives on ordinary maintenance questions.
        store = get_store()
        if store.enabled:
            await run_in_threadpool(
                store.record_turn, endpoint="agent", session_id=body.session_id, query=body.query, answer="",
                llm_provider="none", latency_ms=0.0, input_flagged=True,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query flagged by content safety screening: {input_safety.note}",
        )

    try:
        with Timer() as timer:
            result = await agent_service.run_agent(body.query)
    except Exception as exc:
        logger.exception("Unexpected error during /agent")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    output_safety = safety_service.check_text(result.answer)

    groundedness = None
    if result.llm_used and result.tool_calls:
        source_text = " ".join(tc.result_full or tc.result_excerpt for tc in result.tool_calls)
        groundedness = safety_service.check_groundedness(result.answer, source_text)

    turn_id = None
    store = get_store()
    if store.enabled:
        saved = await run_in_threadpool(
            store.record_turn,
            endpoint="agent",
            session_id=body.session_id,
            query=body.query,
            answer=result.answer,
            llm_provider=result.llm_provider,
            latency_ms=timer.ms,
            cited_chunk_ids=result.structured.cited_chunk_ids if result.structured else [],
            tool_calls=[{"tool": tc.tool, "arguments": tc.arguments} for tc in result.tool_calls],
            input_flagged=input_safety.flagged,
            output_flagged=output_safety.flagged,
            grounded=groundedness.grounded if groundedness else None,
            structured_validated=(result.structured_meta.validated
                                  if result.structured_meta and result.structured_meta.mode == "llm" else None),
            model_needs_review=bool(result.structured and result.structured.needs_human_review),
        )
        turn_id = saved.turn_id

    return AgentResponse(
        query=result.query,
        answer=result.answer,
        llm_used=result.llm_used,
        llm_provider=result.llm_provider,
        tool_calls=[
            AgentToolCall(tool=tc.tool, arguments=tc.arguments, result_excerpt=tc.result_excerpt)
            for tc in result.tool_calls
        ],
        input_safety=input_safety,
        output_safety=output_safety,
        groundedness=groundedness,
        structured=result.structured,
        structured_meta=result.structured_meta,
        turn_id=turn_id,
    )
