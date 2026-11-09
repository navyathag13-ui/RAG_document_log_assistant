"""
Conversation history routes, backed by MongoDB (app/db/conversation_store.py).

GET /history/stats         per-endpoint turns and latency, tool usage, review count
GET /history/review        turns a person should look at, newest first
GET /history/{session_id}  one conversation, oldest first

All three return 503 when MONGODB_URI is not set, so a missing database is
never mistaken for an empty history.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pymongo.errors import PyMongoError

from app.db.conversation_store import get_store

history_router = APIRouter(prefix="/history", tags=["History"])


def _store():
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Conversation history is off: set MONGODB_URI to enable it.")
    return store


def _public(doc: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["turn_id"] = doc["_id"]
    out["created_at"] = doc["created_at"].isoformat()
    return out


async def _call(fn, *args, **kwargs):
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except PyMongoError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"MongoDB unavailable: {type(exc).__name__}")


@history_router.get("/stats")
async def history_stats():
    return await _call(_store().stats)


@history_router.get("/review")
async def review_queue(limit: int = Query(default=50, ge=1, le=500)):
    return [_public(d) for d in await _call(_store().review_queue, limit)]


@history_router.get("/{session_id}")
async def session_history(session_id: str, limit: int = Query(default=50, ge=1, le=500)):
    turns = await _call(_store().session, session_id, limit)
    if not turns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No turns for session '{session_id}'")
    return [_public(d) for d in turns]
