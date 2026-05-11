"""
Initialize the SQLite schema and seed the three built-in prompt templates.

Call init_db() once at application startup (in main.py lifespan).
Re-running is safe — all statements use IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.database import get_db

logger = logging.getLogger(__name__)

# ── DDL ────────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_templates (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    is_builtin  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id                   TEXT PRIMARY KEY,
    query                TEXT NOT NULL,
    prompt_template_id   TEXT,
    prompt_template_name TEXT,
    top_k                INTEGER NOT NULL DEFAULT 5,
    answer               TEXT NOT NULL,
    llm_used             INTEGER NOT NULL DEFAULT 0,
    retrieval_count      INTEGER NOT NULL DEFAULT 0,
    run_type             TEXT NOT NULL DEFAULT 'single',
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id                  TEXT PRIMARY KEY,
    experiment_run_id   TEXT NOT NULL,
    groundedness_score  REAL,
    relevance_score     REAL,
    completeness_score  REAL,
    clarity_score       REAL,
    hallucination_risk  REAL,
    overall_score       REAL,
    method              TEXT NOT NULL DEFAULT 'rule_based',
    details             TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (experiment_run_id)
        REFERENCES experiment_runs(id) ON DELETE CASCADE
);
"""

# ── Seed data ─────────────────────────────────────────────────────────────────

_BUILTIN_TEMPLATES = [
    {
        "id": "technical",
        "name": "Technical Expert",
        "description": "Precise, factual answers with specific values, codes, and step references.",
        "system_prompt": (
            "You are a precise engineering assistant with deep technical expertise.\n"
            "Answer the question using ONLY the information in the provided context.\n"
            "Include specific values, measurements, part numbers, or step references when present.\n"
            "If the context does not contain enough information, say: "
            "\"The provided documents do not contain sufficient information to answer this question.\"\n"
            "Do not speculate or add information not present in the context.\n"
            "Be concise and factual."
        ),
    },
    {
        "id": "detailed",
        "name": "Comprehensive Guide",
        "description": "Thorough explanations with reasoning, context, and cross-document synthesis.",
        "system_prompt": (
            "You are a senior engineering knowledge assistant.\n"
            "Provide thorough, well-structured answers based ONLY on the provided context.\n"
            "Explain not just what to do, but why — referencing specific passages from the documents.\n"
            "Organize your answer with clear sections or numbered steps where appropriate.\n"
            "If multiple documents are relevant, synthesise the information clearly.\n"
            "If context is insufficient, explicitly state what information is missing.\n"
            "Do not invent or infer facts beyond what the context states."
        ),
    },
    {
        "id": "concise",
        "name": "Quick Reference",
        "description": "Brief, direct answers optimised for fast lookup — bullets and steps.",
        "system_prompt": (
            "You are a concise engineering reference assistant.\n"
            "Answer using ONLY the provided context. Be direct and brief.\n"
            "Use bullet points or numbered steps when appropriate.\n"
            "Maximum 3–5 sentences or steps unless more detail is genuinely needed.\n"
            "If the context does not contain the answer, say so in one sentence."
        ),
    },
]


def init_db() -> None:
    """Create tables and seed built-in prompt templates (idempotent)."""
    with get_db() as conn:
        conn.executescript(_SCHEMA)

        now = datetime.now(timezone.utc).isoformat()
        for tmpl in _BUILTIN_TEMPLATES:
            conn.execute(
                """
                INSERT OR IGNORE INTO prompt_templates
                    (id, name, description, system_prompt, is_builtin, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (tmpl["id"], tmpl["name"], tmpl["description"],
                 tmpl["system_prompt"], now, now),
            )

    logger.info("Database initialised — tables and built-in templates ready.")
