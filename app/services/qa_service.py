"""
Question-answering service (v2).

Two modes:
  1. LLM mode  — uses OpenAI (or compatible) API to synthesise a grounded answer
                 from the retrieved context. Supports swappable prompt templates.
  2. Fallback  — when no API key is configured, formats the retrieved chunks
                 into a structured, source-linked response without any LLM call.

v2 additions:
  - answer_with_template(): primary entry point used by /compare and /benchmark.
    Returns (AskResponse, raw_chunks_list) so callers can evaluate the answer.
  - answer(): preserved for backwards compatibility with the original /ask route.
    Now also accepts template_id and auto_evaluate; saves experiments automatically.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import AskResponse, EvalScores, SourceChunk
from app.services.retrieval_service import retrieve

logger = get_logger(__name__)

# Default system prompt kept as fallback when no template is selected
_DEFAULT_SYSTEM_PROMPT = """You are a precise engineering assistant.
Answer the user's question using ONLY the information provided in the context below.
If the context does not contain enough information to answer, say clearly:
"I don't have enough information in the retrieved documents to answer this question."
Never fabricate facts or reference knowledge outside the provided context.
Cite the source document name(s) when possible."""


# ── Primary entry point (v2) ─────────────────────────────────────────────────

def answer_with_template(
    question: str,
    top_k: Optional[int] = None,
    template_id: Optional[str] = None,
) -> tuple[AskResponse, list[dict]]:
    """
    Retrieve, synthesise, and return (AskResponse, raw_chunks_list).

    The raw_chunks list is returned so the caller can pass it to
    evaluation_service.score_answer() without making a second retrieval.

    Parameters
    ----------
    question    : user question
    top_k       : number of chunks to retrieve
    template_id : prompt template ID from the DB; None → default prompt
    """
    chunks = retrieve(question, top_k=top_k)

    sources = [
        SourceChunk(
            chunk_id     = c.chunk_id,
            doc_name     = c.doc_name,
            file_type    = c.file_type,
            text_excerpt = c.text[:300],
            score        = c.score,
        )
        for c in chunks
    ]

    # Resolve system prompt
    system_prompt, template_name = _resolve_template(template_id)

    if settings.OPENAI_API_KEY:
        generated, llm_used = _llm_answer(question, chunks, system_prompt)
    else:
        generated, llm_used = _fallback_answer(question, chunks)

    ask_resp = AskResponse(
        question        = question,
        answer          = generated,
        llm_used        = llm_used,
        retrieval_count = len(chunks),
        sources         = sources,
        template_name   = template_name,
    )

    # Build raw dicts for evaluation service
    raw_chunks = [
        {"text": c.text, "score": c.score, "doc_name": c.doc_name}
        for c in chunks
    ]

    return ask_resp, raw_chunks


# ── Backwards-compatible entry point (v1 /ask route) ─────────────────────────

def answer(
    question: str,
    top_k: Optional[int] = None,
    template_id: Optional[str] = None,
    auto_evaluate: bool = True,
) -> AskResponse:
    """
    Retrieve, synthesise, optionally evaluate, and persist an experiment run.

    This is the function called by POST /ask.  All parameters beyond question
    and top_k are optional so the v1 call signature still works unchanged.
    """
    ask_resp, raw_chunks = answer_with_template(
        question=question,
        top_k=top_k,
        template_id=template_id,
    )

    # ── Auto-evaluate and persist ─────────────────────────────────────────────
    try:
        from app.services import evaluation_service, experiment_service
        from app.services.prompt_service import get_template

        # Resolve template name for the experiment record
        tmpl = get_template(template_id) if template_id else None
        tmpl_name = tmpl["name"] if tmpl else "Default"

        eval_scores = None
        if auto_evaluate:
            scores_dict = evaluation_service.score_answer(
                question=question,
                answer=ask_resp.answer,
                chunks=raw_chunks,
            )
            eval_scores = EvalScores(**{k: v for k, v in scores_dict.items() if k != "details"})

        run_id = experiment_service.save_run(
            query                = question,
            answer               = ask_resp.answer,
            prompt_template_id   = template_id,
            prompt_template_name = tmpl_name,
            top_k                = top_k or settings.DEFAULT_TOP_K,
            llm_used             = ask_resp.llm_used,
            retrieval_count      = ask_resp.retrieval_count,
            run_type             = "single",
        )

        if auto_evaluate and eval_scores:
            evaluation_service.save_evaluation(run_id, scores_dict)

        # Enrich response with eval data
        ask_resp.evaluation         = eval_scores
        ask_resp.experiment_run_id  = run_id

    except Exception as exc:
        # Never let tracking errors break the primary /ask response
        logger.warning("Experiment tracking failed (non-fatal): %s", exc)

    return ask_resp


# ── LLM answer ────────────────────────────────────────────────────────────────

def _llm_answer(question: str, chunks, system_prompt: str) -> tuple[str, bool]:
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed; falling back to retrieval-only mode.")
        return _fallback_answer(question, chunks)

    context      = _build_context(chunks)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        client = OpenAI(
            api_key  = settings.OPENAI_API_KEY,
            base_url = settings.OPENAI_BASE_URL,
        )
        response = client.chat.completions.create(
            model    = settings.OPENAI_MODEL,
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature = 0.1,
            max_tokens  = 600,
        )
        answer_text = response.choices[0].message.content.strip()
        logger.info("LLM answer generated (%d chars).", len(answer_text))
        return answer_text, True

    except Exception as exc:
        logger.warning("LLM call failed (%s); falling back to retrieval-only mode.", exc)
        return _fallback_answer(question, chunks)


# ── Fallback answer (no LLM) ─────────────────────────────────────────────────

def _fallback_answer(question: str, chunks) -> tuple[str, bool]:
    """
    Compose an answer directly from the top-ranked retrieved chunks.
    Clearly labels itself as retrieval-based, not LLM-synthesised.
    """
    if not chunks:
        return (
            "No relevant content was found in the indexed documents for this question.",
            False,
        )

    lines = [
        "⚠️  LLM synthesis is not enabled (no OPENAI_API_KEY configured).",
        "The following excerpts were retrieved from the most relevant document sections:",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] Source: {chunk.doc_name}  (relevance: {chunk.score:.2f})")
        excerpt = chunk.text[:400].strip()
        if len(chunk.text) > 400:
            excerpt += " …"
        lines.append(excerpt)
        lines.append("")

    lines.append(
        "To get a synthesised, prose answer, add your OPENAI_API_KEY to the .env file."
    )
    return "\n".join(lines), False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_template(template_id: Optional[str]) -> tuple[str, Optional[str]]:
    """
    Return (system_prompt, template_name).
    Falls back to _DEFAULT_SYSTEM_PROMPT if template not found.
    """
    if template_id:
        try:
            from app.services.prompt_service import get_template
            tmpl = get_template(template_id)
            if tmpl:
                return tmpl["system_prompt"], tmpl["name"]
        except Exception as exc:
            logger.warning("Could not load template '%s': %s", template_id, exc)
    return _DEFAULT_SYSTEM_PROMPT, None


def _build_context(chunks) -> str:
    """Concatenate retrieved chunks into a single context string for the LLM."""
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        entry  = f"[Source: {chunk.doc_name}]\n{chunk.text}"
        total += len(entry)
        if total > settings.MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
    return "\n\n---\n\n".join(parts)
