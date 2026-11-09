"""
Conversation history and agent traces in MongoDB.

Every /ask and /agent turn is saved as one document: the question, the answer,
which provider answered, the chunks it cited, every tool the agent called, the
safety and groundedness results and how long it took. Turns vary a lot in shape
(an /ask turn has sources and no tool calls, an agent turn can have zero to five
tool calls, each with its own arguments), which is why they live in a document
store and not in the SQLite experiment tables.

What this makes possible:
  - GET /history/{session_id}  replay a conversation in order
  - GET /history/review        turns a person should look at (flagged, ungrounded,
                               invalid structured output or marked needs_human_review)
  - GET /history/stats         per-endpoint counts and latency plus how often each
                               tool is called, computed by a MongoDB aggregation

MongoDB is optional. With MONGODB_URI unset the store is disabled and the app
behaves exactly as before. If MongoDB is configured but unreachable, saving a turn
logs a warning and the request still succeeds: history must never take the
assistant down.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

COLLECTION = "turns"


@dataclass
class SaveResult:
    saved: bool
    turn_id: Optional[str] = None
    error: Optional[str] = None


def needs_review(doc: dict[str, Any]) -> list[str]:
    """Reasons a saved turn should be looked at by a person (empty list = fine)."""
    reasons = []
    if doc.get("input_flagged") or doc.get("output_flagged"):
        reasons.append("content safety flag")
    if doc.get("grounded") is False:
        reasons.append("answer not grounded in its sources")
    if doc.get("structured_validated") is False:
        reasons.append("structured output failed validation")
    if doc.get("model_needs_review"):
        reasons.append("model asked for human review")
    return reasons


class ConversationStore:
    def __init__(self, collection: Optional[Collection]):
        self._col = collection
        self._indexed = False

    @property
    def enabled(self) -> bool:
        return self._col is not None

    def _ensure_indexes(self) -> None:
        if self._indexed or self._col is None:
            return
        self._col.create_index([("session_id", ASCENDING), ("created_at", ASCENDING)])
        self._col.create_index([("endpoint", ASCENDING), ("created_at", DESCENDING)])
        self._col.create_index([("review_reasons", ASCENDING)], sparse=True)
        self._indexed = True

    # ── writes ────────────────────────────────────────────────────────────────

    def record_turn(self, *, endpoint: str, session_id: Optional[str], query: str, answer: str,
                    llm_provider: str, latency_ms: float, cited_chunk_ids: Optional[list[str]] = None,
                    tool_calls: Optional[list[dict[str, Any]]] = None, input_flagged: bool = False,
                    output_flagged: bool = False, grounded: Optional[bool] = None,
                    structured_validated: Optional[bool] = None, model_needs_review: bool = False) -> SaveResult:
        if self._col is None:
            return SaveResult(saved=False, error="MongoDB not configured")
        doc: dict[str, Any] = {
            "_id": uuid.uuid4().hex,
            "session_id": session_id or "default",
            "endpoint": endpoint,
            "query": query,
            "answer": answer,
            "llm_provider": llm_provider,
            "latency_ms": round(float(latency_ms), 1),
            "cited_chunk_ids": cited_chunk_ids or [],
            "tool_calls": tool_calls or [],
            "n_tool_calls": len(tool_calls or []),
            "input_flagged": input_flagged,
            "output_flagged": output_flagged,
            "grounded": grounded,
            "structured_validated": structured_validated,
            "model_needs_review": model_needs_review,
            "created_at": datetime.now(timezone.utc),
        }
        reasons = needs_review(doc)
        if reasons:
            doc["review_reasons"] = reasons  # field absent when fine, so the sparse index stays small
        try:
            self._ensure_indexes()
            self._col.insert_one(doc)
        except PyMongoError as exc:
            logger.warning("Could not save %s turn to MongoDB: %s", endpoint, exc)
            return SaveResult(saved=False, error=type(exc).__name__)
        return SaveResult(saved=True, turn_id=doc["_id"])

    # ── reads ─────────────────────────────────────────────────────────────────

    def session(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._col is None:
            return []
        return list(self._col.find({"session_id": session_id}).sort("created_at", ASCENDING).limit(limit))

    def review_queue(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._col is None:
            return []
        return list(self._col.find({"review_reasons": {"$exists": True}}).sort("created_at", DESCENDING).limit(limit))

    def stats(self) -> dict[str, Any]:
        """Per-endpoint counts and latency, and how often each tool is called."""
        if self._col is None:
            return {"by_endpoint": [], "tool_usage": [], "review_count": 0}
        by_endpoint = list(self._col.aggregate([
            {"$group": {"_id": "$endpoint", "turns": {"$sum": 1}, "avg_latency_ms": {"$avg": "$latency_ms"},
                        "max_latency_ms": {"$max": "$latency_ms"}, "avg_tool_calls": {"$avg": "$n_tool_calls"}}},
            {"$sort": {"_id": 1}},
        ]))
        tool_usage = list(self._col.aggregate([
            {"$unwind": "$tool_calls"},
            {"$group": {"_id": "$tool_calls.tool", "calls": {"$sum": 1}}},
            {"$sort": {"calls": -1, "_id": 1}},
        ]))
        return {
            "by_endpoint": [{"endpoint": r["_id"], "turns": r["turns"],
                             "avg_latency_ms": round(r["avg_latency_ms"] or 0.0, 1),
                             "max_latency_ms": r["max_latency_ms"],
                             "avg_tool_calls": round(r["avg_tool_calls"] or 0.0, 2)} for r in by_endpoint],
            "tool_usage": [{"tool": r["_id"], "calls": r["calls"]} for r in tool_usage],
            "review_count": self._col.count_documents({"review_reasons": {"$exists": True}}),
        }


_store: Optional[ConversationStore] = None


def get_store() -> ConversationStore:
    """The process-wide store, created on first use from MONGODB_URI."""
    global _store
    if _store is None:
        if not settings.MONGODB_URI:
            _store = ConversationStore(None)
        else:
            client: MongoClient = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=settings.MONGODB_TIMEOUT_MS,
                                              tz_aware=True)
            _store = ConversationStore(client[settings.MONGODB_DB][COLLECTION])
    return _store


def set_store(store: Optional[ConversationStore]) -> None:
    """Swap the store (tests use this to inject an in-memory or test database)."""
    global _store
    _store = store


class Timer:
    """`with Timer() as t: ...` then t.ms"""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000.0
