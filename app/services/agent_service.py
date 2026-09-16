"""
Agent orchestration via Semantic Kernel — real function calling, not a
hardcoded router.

The agent has two tools:

  search_documents(query, top_k)        Wraps the existing retrieval
                                         pipeline (retrieval_service.py) —
                                         the same ChromaDB + sentence-
                                         transformers search the rest of
                                         the app uses.

  check_equipment_status(equipment_id)  A MOCK second data source: fixed,
                                         hand-written JSON for a small set
                                         of equipment IDs, simulating what
                                         a real CMMS/SCADA status lookup
                                         would return. This is explicitly
                                         NOT live data — it exists to give
                                         the model a second, genuinely
                                         different tool to choose between,
                                         so tool selection is a real
                                         decision and not just "call the
                                         one tool that exists."

The model (via whichever backend app.services.llm_service resolves — Azure
OpenAI or OpenAI) decides per query whether to call one tool, both, or
neither, using Semantic Kernel's automatic function calling
(FunctionChoiceBehavior.Auto()). The plugins are registered on the kernel
and the model's own tool-use decision selects which one(s) run, based on
the actual query text — this is not an if/else keyword router pretending
to be agentic. If the query is ambiguous, the system prompt instructs the
model to ask a clarifying question instead of guessing or calling a tool
speculatively; that shows up as a plain-text response with an empty tool
trace, which is a legitimate, inspectable outcome, not a failure.

Every function invocation is captured by a Semantic Kernel FUNCTION_INVOCATION
filter, so the full decision trace — which tool, what arguments, what it
returned — is inspectable via the API response and the log, not just the
final answer. That's the actual point of this phase: a black-box "agent"
that no one can audit isn't more trustworthy than a plain LLM call.

Honesty note: if no LLM backend is configured, there is no model available
to make a tool-use decision, so this module does not fake one. run_agent()
returns a clearly labeled message saying agent mode needs an LLM backend —
the same pattern qa_service.py uses for its own offline fallback, not a
silent degradation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Annotated, Any

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory
from semantic_kernel.filters import FilterTypes
from semantic_kernel.filters.functions.function_invocation_context import FunctionInvocationContext
from semantic_kernel.functions import kernel_function

from app.core.logging_config import get_logger
from app.services import llm_service
from app.services.retrieval_service import retrieve

logger = get_logger(__name__)


# ── System prompt ────────────────────────────────────────────────────────────

_AGENT_SYSTEM_PROMPT = """You are an engineering assistant with two tools available:

1. search_documents — searches indexed manuals, troubleshooting guides, logs, and notes.
2. check_equipment_status — looks up a specific piece of equipment's current status by ID.

Decide which tool(s), if any, the question actually needs. Call search_documents
for "how do I / why does / what is the procedure for / what does fault code X
mean" type questions. Call check_equipment_status only when the user asks about
a specific piece of equipment's current state and gives (or clearly implies)
an equipment ID. Call both if the question genuinely needs both.

If the question is ambiguous — for example it says "the pump" or "it" without
saying which equipment, or it's too vague to search effectively — do NOT guess
and do NOT call a tool speculatively. Instead, ask exactly one specific
clarifying question and stop there.

Never fabricate information beyond what a tool returned. If a tool returns
nothing useful, say so plainly instead of making something up."""


# ── Mock second data source (Phase 2 requirement: a second, non-RAG tool) ────

_MOCK_EQUIPMENT_DB: dict[str, dict[str, Any]] = {
    "HX-9000": {
        "equipment_id": "HX-9000",
        "status": "operational",
        "last_maintenance": "2024-02-15",
        "current_fault_codes": [],
        "operating_hours": 8420,
    },
    "SCU-400": {
        "equipment_id": "SCU-400",
        "status": "fault",
        "last_maintenance": "2024-01-10",
        "current_fault_codes": ["FAULT-T02"],
        "operating_hours": 15230,
    },
    "PUMP-01": {
        "equipment_id": "PUMP-01",
        "status": "warning",
        "last_maintenance": "2024-03-01",
        "current_fault_codes": ["WARN-T01"],
        "operating_hours": 6011,
    },
}


class DocumentSearchPlugin:
    """Exposes the existing retrieval pipeline as a Semantic Kernel tool."""

    @kernel_function(
        name="search_documents",
        description=(
            "Search the indexed engineering documents (manuals, troubleshooting "
            "guides, logs, notes) for passages relevant to a query. Use this for "
            "how/why/procedure/specification questions answered by documentation."
        ),
    )
    def search_documents(
        self,
        query: Annotated[str, "The search query, in natural language"],
        top_k: Annotated[int, "Number of chunks to retrieve"] = 4,
    ) -> str:
        try:
            results = retrieve(query, top_k=top_k)
        except ValueError as exc:
            return f"No documents are indexed yet: {exc}"

        if not results:
            return "No relevant passages found in the indexed documents."

        lines = [
            f"[{r.doc_name} | relevance={r.score:.2f}] {r.text[:400]}"
            for r in results
        ]
        return "\n\n".join(lines)


class EquipmentStatusPlugin:
    """
    A MOCK second data source. Returns fixed JSON for a small set of known
    equipment IDs, simulating a CMMS/SCADA status lookup — not a live system.
    Exists to give the agent a genuinely different second tool to choose
    between, so tool selection is a real decision.
    """

    @kernel_function(
        name="check_equipment_status",
        description=(
            "Look up the current status of a piece of equipment by its ID "
            "(e.g. 'HX-9000', 'SCU-400', 'PUMP-01') — status, active fault "
            "codes, last maintenance date, operating hours. Use this when the "
            "question is about a specific machine's current state, not "
            "documentation. This is simulated/mock data, not a live feed."
        ),
    )
    def check_equipment_status(
        self,
        equipment_id: Annotated[str, "Equipment identifier, e.g. 'HX-9000'"],
    ) -> str:
        key = equipment_id.strip().upper()
        record = _MOCK_EQUIPMENT_DB.get(key)
        if record is None:
            return json.dumps(
                {
                    "equipment_id": key,
                    "status": "unknown",
                    "note": "No record for this equipment ID in the mock status system.",
                }
            )
        return json.dumps(record)


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    tool: str
    arguments: dict[str, Any]
    result_excerpt: str


@dataclass
class AgentResult:
    query: str
    answer: str
    llm_used: bool
    llm_provider: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


# ── Orchestration ─────────────────────────────────────────────────────────────

async def run_agent(query: str) -> AgentResult:
    """
    Run one agent turn: build a kernel with both tools registered, let the
    configured LLM decide what (if anything) to call, and return the final
    answer plus the full, inspectable tool-call trace.
    """
    resolved = llm_service.resolve()

    if resolved.provider == "none":
        logger.info("Agent mode requested with no LLM backend configured; declining.")
        return AgentResult(
            query=query,
            answer=(
                "Agent orchestration needs a configured LLM backend (Azure OpenAI "
                "or OpenAI) to decide which tool to call — there is no model "
                "available right now to make that decision, and this project does "
                "not fake agentic behavior without one. Configure AZURE_OPENAI_* "
                "or OPENAI_API_KEY in .env, or use POST /ask for retrieval-only mode."
            ),
            llm_used=False,
            llm_provider="none",
        )

    kernel = Kernel()

    if resolved.provider == "azure_openai":
        chat_service = AzureChatCompletion(
            service_id="agent",
            deployment_name=resolved.model,
            endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            api_version=resolved.api_version,
        )
        execution_settings = AzureChatPromptExecutionSettings(service_id="agent")
    else:
        chat_service = OpenAIChatCompletion(
            service_id="agent",
            ai_model_id=resolved.model,
            api_key=resolved.api_key,
        )
        execution_settings = OpenAIChatPromptExecutionSettings(service_id="agent")

    kernel.add_service(chat_service)
    kernel.add_plugin(DocumentSearchPlugin(), plugin_name="documents")
    kernel.add_plugin(EquipmentStatusPlugin(), plugin_name="equipment")

    execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    trace: list[ToolCallRecord] = []

    async def log_tool_call(context: FunctionInvocationContext, next):
        await next(context)
        args = {
            k: v for k, v in dict(context.arguments).items()
            if not str(k).startswith("chat_history")
        }
        result_text = str(context.result) if context.result is not None else ""
        record = ToolCallRecord(
            tool=f"{context.function.plugin_name}.{context.function.name}",
            arguments=args,
            result_excerpt=result_text[:300],
        )
        trace.append(record)
        logger.info(
            "Agent tool call: %s(%s) -> %s",
            record.tool, args, result_text[:150],
        )

    kernel.add_filter(FilterTypes.FUNCTION_INVOCATION, log_tool_call)

    history = ChatHistory()
    history.add_system_message(_AGENT_SYSTEM_PROMPT)
    history.add_user_message(query)

    try:
        result = await chat_service.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
        )
        answer = str(result) if result is not None else ""
        logger.info(
            "Agent turn complete via %s: %d tool call(s), answer %d chars.",
            resolved.provider, len(trace), len(answer),
        )
        return AgentResult(
            query=query,
            answer=answer,
            llm_used=True,
            llm_provider=resolved.provider,
            tool_calls=trace,
        )
    except Exception as exc:
        logger.warning("Agent LLM call via %s failed: %s", resolved.provider, exc)
        return AgentResult(
            query=query,
            answer=f"The agent's LLM call failed ({resolved.provider}): {exc}",
            llm_used=False,
            llm_provider=resolved.provider,
            tool_calls=trace,
        )
