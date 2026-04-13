"""
Question-answering service.

Two modes:
  1. LLM mode  — uses OpenAI (or compatible) API to synthesise a grounded answer
                 from the retrieved context.
  2. Fallback  — when no API key is configured, formats the retrieved chunks
                 into a structured, source-linked response without any LLM call.
                 The pipeline (chunking, embedding, retrieval) still runs fully.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import AskResponse, SourceChunk
from app.services.retrieval_service import retrieve

logger = get_logger(__name__)

# System prompt instructs the LLM to answer only from context
_SYSTEM_PROMPT = """You are a precise engineering assistant.
Answer the user's question using ONLY the information provided in the context below.
If the context does not contain enough information to answer, say clearly:
"I don't have enough information in the retrieved documents to answer this question."
Never fabricate facts or reference knowledge outside the provided context.
Cite the source document name(s) when possible."""


def answer(question: str, top_k: int | None = None) -> AskResponse:
    """
    Retrieve relevant chunks, then generate (or compose) an answer.
    """
    chunks = retrieve(question, top_k=top_k)

    sources = [
        SourceChunk(
            chunk_id=c.chunk_id,
            doc_name=c.doc_name,
            file_type=c.file_type,
            text_excerpt=c.text[:300],
            score=c.score,
        )
        for c in chunks
    ]

    if settings.OPENAI_API_KEY:
        generated, llm_used = _llm_answer(question, chunks)
    else:
        generated, llm_used = _fallback_answer(question, chunks)

    return AskResponse(
        question=question,
        answer=generated,
        llm_used=llm_used,
        retrieval_count=len(chunks),
        sources=sources,
    )


# ── LLM answer ───────────────────────────────────────────────────────────────────

def _llm_answer(question: str, chunks) -> tuple[str, bool]:
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed; falling back to retrieval-only mode.")
        return _fallback_answer(question, chunks)

    context = _build_context(chunks)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        answer_text = response.choices[0].message.content.strip()
        logger.info("LLM answer generated (%d chars).", len(answer_text))
        return answer_text, True

    except Exception as exc:
        logger.warning("LLM call failed (%s); falling back to retrieval-only mode.", exc)
        return _fallback_answer(question, chunks)


# ── Fallback answer (no LLM) ─────────────────────────────────────────────────────

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
        # Show up to 400 characters per chunk
        excerpt = chunk.text[:400].strip()
        if len(chunk.text) > 400:
            excerpt += " …"
        lines.append(excerpt)
        lines.append("")

    lines.append(
        "To get a synthesised, prose answer, add your OPENAI_API_KEY to the .env file."
    )
    return "\n".join(lines), False


# ── Helpers ────────────────────────────────────────────────────────────────────────

def _build_context(chunks) -> str:
    """Concatenate retrieved chunks into a single context string for the LLM."""
    parts = []
    total = 0
    for chunk in chunks:
        entry = f"[Source: {chunk.doc_name}]\n{chunk.text}"
        total += len(entry)
        if total > settings.MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
    return "\n\n---\n\n".join(parts)
