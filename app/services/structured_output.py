"""
Schema-validated LLM output for /ask and /agent.

The model is asked for a JSON object matching STRUCTURED_ANSWER_SCHEMA, sent
as an Azure OpenAI / OpenAI structured-outputs `response_format`
(type=json_schema, strict=true). The reply is then validated a second time
in Python with the StructuredAnswer Pydantic model, because a strict schema
guarantees shape, not meaning:

  - confidence must be in [0, 1] (strict mode doesn't support min/max, so
    the JSON schema can't enforce it)
  - every cited_chunk_id must be one of the IDs the model was actually shown
    in this request — a made-up or mistyped citation is a validation error,
    not something we pass to the user

When validation fails, the model is called once more with the validation
error appended to the conversation. If the retry fails too, the caller gets
a fallback StructuredAnswer (no citations, confidence 0, needs_human_review
true) and StructuredMeta.fallback_used=true, so a bad model reply is always
visible in the response instead of silently breaking the endpoint.
"""
from __future__ import annotations

import json
from typing import Awaitable, Callable, Optional

from pydantic import ValidationError

from app.core.logging_config import get_logger
from app.models.schemas import StructuredAnswer, StructuredMeta

logger = get_logger(__name__)

MAX_RETRIES = 1

# Written by hand rather than generated from StructuredAnswer.model_json_schema()
# because strict mode rejects keywords like minimum/maximum that Pydantic emits.
STRUCTURED_ANSWER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The answer to the user's question, using only the provided context.",
        },
        "cited_chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "IDs of the context entries the answer relies on, copied exactly. Empty if none.",
        },
        "confidence": {
            "type": "number",
            "description": "How well the context supports the answer, from 0.0 (not at all) to 1.0 (fully).",
        },
        "needs_human_review": {
            "type": "boolean",
            "description": "True if the context is insufficient, contradictory, or the answer is safety-critical.",
        },
    },
    "required": ["answer", "cited_chunk_ids", "confidence", "needs_human_review"],
    "additionalProperties": False,
}

RESPONSE_FORMAT: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "structured_answer",
        "strict": True,
        "schema": STRUCTURED_ANSWER_SCHEMA,
    },
}

FORMAT_INSTRUCTIONS = """
Reply with a JSON object with exactly these fields:
  answer             - your answer
  cited_chunk_ids    - the chunk_id values of the context entries you used, copied exactly
  confidence         - a number from 0.0 to 1.0 for how well the context supports the answer
  needs_human_review - true if the context is insufficient, contradictory, or the answer is safety-critical"""


def parse(raw: str, allowed_ids: set[str]) -> StructuredAnswer:
    """Parse and validate one model reply. Raises ValueError/ValidationError if invalid."""
    data = json.loads(raw)
    return StructuredAnswer.model_validate(data, context={"allowed_ids": allowed_ids})


def fallback(raw: Optional[str], error: str) -> StructuredAnswer:
    """What callers get when every attempt failed validation."""
    text = (raw or "").strip() or "The model did not return a usable answer."
    logger.warning("Structured output failed validation after retries; using fallback. Last error: %s", error)
    return StructuredAnswer(answer=text, cited_chunk_ids=[], confidence=0.0, needs_human_review=True)


def _feedback(error: str) -> str:
    return (
        f"Your previous reply failed validation: {error}\n"
        "Reply again with only a JSON object matching the required schema. "
        "Only cite chunk_id values that appear in the context."
    )


def _short(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'root'}: {e['msg']}" for e in exc.errors())
    return f"{type(exc).__name__}: {exc}"


def generate(
    call: Callable[[Optional[str]], str],
    allowed_ids: set[str],
    max_retries: int = MAX_RETRIES,
) -> tuple[StructuredAnswer, StructuredMeta]:
    """
    call(None) produces the first raw reply; call(feedback) produces a retry
    after the model is told what was wrong. Returns (answer, meta).
    """
    raw, error = None, ""
    for attempt in range(1, max_retries + 2):
        raw = call(_feedback(error) if attempt > 1 else None)
        try:
            return parse(raw, allowed_ids), StructuredMeta(validated=True, attempts=attempt)
        except (ValueError, ValidationError) as exc:
            error = _short(exc)
            logger.info("Structured output attempt %d invalid: %s", attempt, error)
    return fallback(raw, error), StructuredMeta(
        validated=False, attempts=max_retries + 1, fallback_used=True, last_error=error,
    )


async def generate_async(
    call: Callable[[Optional[str]], Awaitable[str]],
    allowed_ids: set[str],
    max_retries: int = MAX_RETRIES,
) -> tuple[StructuredAnswer, StructuredMeta]:
    """Async counterpart of generate()."""
    raw, error = None, ""
    for attempt in range(1, max_retries + 2):
        raw = await call(_feedback(error) if attempt > 1 else None)
        try:
            return parse(raw, allowed_ids), StructuredMeta(validated=True, attempts=attempt)
        except (ValueError, ValidationError) as exc:
            error = _short(exc)
            logger.info("Structured output attempt %d invalid: %s", attempt, error)
    return fallback(raw, error), StructuredMeta(
        validated=False, attempts=max_retries + 1, fallback_used=True, last_error=error,
    )


def offline(answer_text: str, chunks) -> tuple[StructuredAnswer, StructuredMeta]:
    """
    Structured view of the retrieval-only fallback: no model wrote anything,
    so there's nothing to validate. The cited IDs are simply the retrieved
    chunks, confidence is 0 and review is required.
    """
    return (
        StructuredAnswer(
            answer=answer_text,
            cited_chunk_ids=[c.chunk_id for c in chunks],
            confidence=0.0,
            needs_human_review=True,
        ),
        StructuredMeta(validated=False, attempts=0, mode="offline"),
    )
