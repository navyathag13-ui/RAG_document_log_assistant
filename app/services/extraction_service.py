"""
Structured field extraction from a maintenance work-order document.

POST /extract takes a work order or service report (.pdf, .txt, .md, .log) and
returns its key fields as validated JSON:

  equipment_id, work_date, technician, parts (name + quantity),
  downtime_hours, status, needs_human_review

The model fills a strict JSON schema (Azure OpenAI / OpenAI structured
outputs), but a strict schema only guarantees shape. Every value is then
checked against the source text before anyone sees it:

  - equipment_id, technician and each part name must actually appear in the
    document (a value the model made up is a validation error)
  - work_date must be a real ISO date whose year and day appear in the document
  - quantities must be whole numbers from 1 to 1000; downtime from 0 to 720 hours

A reply that fails is sent back once with the errors listed. If the retry
fails too, the caller gets every field empty with needs_human_review=true and
the errors attached, so a bad extraction is never passed off as a good one.
needs_human_review is also forced on when the equipment or date is missing,
because a record without them can't be filed.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from app.core.logging_config import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 1


class ExtractedPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1, le=1000)

    @field_validator("name")
    @classmethod
    def _name_in_source(cls, v: str, info: ValidationInfo) -> str:
        src = (info.context or {}).get("source")
        if src is not None and not _phrase_in(v, src):
            raise ValueError(f"part '{v}' does not appear in the document")
        return v


class WorkOrderFields(BaseModel):
    """Validated with context={"source": <document text>} to check grounding."""
    model_config = ConfigDict(extra="forbid")

    equipment_id: Optional[str] = None
    work_date: Optional[str] = None
    technician: Optional[str] = None
    parts: list[ExtractedPart] = Field(default_factory=list)
    downtime_hours: Optional[float] = Field(default=None, ge=0, le=720)
    status: Optional[Literal["resolved", "follow_up_required"]] = None
    needs_human_review: bool

    @field_validator("equipment_id")
    @classmethod
    def _equipment_in_source(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        src = (info.context or {}).get("source")
        if v is not None and src is not None and _squash(v) not in _squash(src):
            raise ValueError(f"equipment_id '{v}' does not appear in the document")
        return v

    @field_validator("technician")
    @classmethod
    def _technician_in_source(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        src = (info.context or {}).get("source")
        if v is not None and src is not None:
            missing = [w for w in re.findall(r"[A-Za-z]+", v) if len(w) > 1 and w.lower() not in src.lower()]
            if missing:
                raise ValueError(f"technician '{v}' does not appear in the document")
        return v

    @field_validator("work_date")
    @classmethod
    def _date_real_and_in_source(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return v
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"work_date '{v}' is not a YYYY-MM-DD date")
        src = (info.context or {}).get("source")
        if src is not None:
            if str(d.year) not in src and f"/{d.year % 100:02d}" not in src:
                raise ValueError(f"work_date year {d.year} does not appear in the document")
            if not re.search(rf"(?<!\d)0?{d.day}(?!\d)", src):
                raise ValueError(f"work_date day {d.day} does not appear in the document")
        return v


class ExtractionMeta(BaseModel):
    mode: str = Field(default="llm", description="'llm', or 'offline' when no model is configured")
    validated: bool
    attempts: int
    fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    filename: str
    provider: str = Field(description="LLM backend used: azure_openai, bedrock, openai or none")
    fields: WorkOrderFields
    meta: ExtractionMeta


EXTRACTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "equipment_id": {"type": ["string", "null"], "description": "Only the asset ID code as written, e.g. PMP-104, without the equipment name. Null if no ID is stated."},
        "work_date": {"type": ["string", "null"], "description": "Date the work was done, converted to YYYY-MM-DD (e.g. March 3, 2026 -> 2026-03-03). Null if not stated."},
        "technician": {"type": ["string", "null"], "description": "Full name of the technician who did the work. Null if not stated."},
        "parts": {
            "type": "array",
            "description": "Parts installed or replaced in this job (not parts only mentioned or ordered). Empty if none.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Part name as written in the document"},
                    "quantity": {"type": "integer", "description": "How many were installed"},
                },
                "required": ["name", "quantity"],
                "additionalProperties": False,
            },
        },
        "downtime_hours": {"type": ["number", "null"], "description": "Hours the equipment was out of service (convert minutes; 0 if the document says no downtime). Labor time is not downtime. Null if not stated."},
        "status": {"type": ["string", "null"], "enum": ["resolved", "follow_up_required", None], "description": "resolved if the job is closed or complete; follow_up_required if the fault remains or the job waits on parts or a return visit. Null only if the document gives no outcome."},
        "needs_human_review": {"type": "boolean", "description": "True if anything is ambiguous, contradictory or hard to read."},
    },
    "required": ["equipment_id", "work_date", "technician", "parts", "downtime_hours", "status", "needs_human_review"],
    "additionalProperties": False,
}

RESPONSE_FORMAT: dict = {
    "type": "json_schema",
    "json_schema": {"name": "work_order_fields", "strict": True, "schema": EXTRACTION_SCHEMA},
}

SYSTEM_PROMPT = """You extract fields from maintenance work orders and service reports.
Use only what the document says. If a field is not stated, return null for it; never guess.
Only list parts that were installed or replaced in this job, with the quantity installed.
Set needs_human_review to true if anything is ambiguous, contradictory or hard to read.
Reply with a JSON object matching the schema."""


def build_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Document:\n\"\"\"\n{text}\n\"\"\""},
    ]


def parse(raw: str, source: str) -> WorkOrderFields:
    """Parse and validate one model reply against the document. Raises on any problem."""
    fields = WorkOrderFields.model_validate(json.loads(raw), context={"source": source})
    if fields.equipment_id is None or fields.work_date is None:
        fields.needs_human_review = True
    return fields


def empty(errors: list[str], mode: str = "llm", attempts: int = 0) -> tuple[WorkOrderFields, ExtractionMeta]:
    return (
        WorkOrderFields(needs_human_review=True),
        ExtractionMeta(mode=mode, validated=False, attempts=attempts, fallback_used=mode == "llm", errors=errors),
    )


def _errors(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        return [f"{'.'.join(map(str, e['loc'])) or 'root'}: {e['msg'].removeprefix('Value error, ')}" for e in exc.errors()]
    return [f"{type(exc).__name__}: {exc}"]


def _feedback(errors: list[str]) -> str:
    return (
        "Your previous reply failed validation against the document:\n- "
        + "\n- ".join(errors)
        + "\nReply again with only the JSON object. Use null for anything the document does not state."
    )


def generate(call: Callable[[Optional[str]], str], source: str, max_retries: int = MAX_RETRIES) -> tuple[WorkOrderFields, ExtractionMeta]:
    """call(None) gives the first raw reply; call(feedback) gives a retry after the model sees its errors."""
    errors: list[str] = []
    for attempt in range(1, max_retries + 2):
        raw = call(_feedback(errors) if attempt > 1 else None)
        try:
            return parse(raw, source), ExtractionMeta(validated=True, attempts=attempt)
        except (ValueError, ValidationError) as exc:
            errors = _errors(exc)
            logger.info("Extraction attempt %d invalid: %s", attempt, errors)
    logger.warning("Extraction failed validation after retries: %s", errors)
    return empty(errors, attempts=max_retries + 1)


def extract(text: str, client=None, model: str = "") -> tuple[WorkOrderFields, ExtractionMeta, str]:
    """Extract fields from document text with the configured LLM. Returns (fields, meta, provider)."""
    provider = "custom"
    if client is None:
        from app.services import llm_service

        client, model, provider = llm_service.get_chat_client()
    if client is None:
        return (*empty(["No LLM backend is configured, so nothing was extracted."], mode="offline"), "none")

    messages = build_messages(text)

    def call(feedback: Optional[str]) -> str:
        msgs = list(messages)
        if feedback:
            msgs.append({"role": "user", "content": feedback})
        response = client.chat.completions.create(
            model=model, messages=msgs, temperature=0, response_format=RESPONSE_FORMAT,
        )
        return response.choices[0].message.content or ""

    fields, meta = generate(call, text)
    return fields, meta, provider


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _phrase_in(phrase: str, source: str) -> bool:
    """True if every word of the phrase appears in the source (singular or plural)."""
    src = source.lower()
    for word in re.findall(r"[a-z0-9]+", phrase.lower()):
        stem = word[:-1] if word.endswith("s") and len(word) > 3 else word
        if stem not in src:
            return False
    return True
