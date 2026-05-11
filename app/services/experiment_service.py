"""
Experiment run tracking service.

Every call to /ask and /compare is saved as an experiment_run so the
system builds up a history of queries, answers, prompt versions, and
evaluation scores that can be reviewed and compared later.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db.database import get_db

logger = logging.getLogger(__name__)


def save_run(
    query: str,
    answer: str,
    prompt_template_id: Optional[str],
    prompt_template_name: Optional[str],
    top_k: int,
    llm_used: bool,
    retrieval_count: int,
    run_type: str = "single",   # "single" | "compare" | "benchmark"
) -> str:
    """Persist one experiment run. Returns the new run ID."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO experiment_runs
                (id, query, prompt_template_id, prompt_template_name,
                 top_k, answer, llm_used, retrieval_count, run_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                query,
                prompt_template_id,
                prompt_template_name,
                top_k,
                answer,
                1 if llm_used else 0,
                retrieval_count,
                run_type,
                now,
            ),
        )

    logger.debug("Saved experiment run %s (%s)", run_id, run_type)
    return run_id


def get_runs(
    limit: int = 50,
    offset: int = 0,
    run_type: Optional[str] = None,
) -> list[dict]:
    """Return experiment runs joined with their evaluation scores."""
    query = """
        SELECT
            r.id, r.query, r.prompt_template_id, r.prompt_template_name,
            r.top_k, r.answer, r.llm_used, r.retrieval_count,
            r.run_type, r.created_at,
            e.groundedness_score, e.relevance_score, e.completeness_score,
            e.clarity_score, e.hallucination_risk, e.overall_score,
            e.method AS eval_method
        FROM experiment_runs r
        LEFT JOIN evaluation_results e ON e.experiment_run_id = r.id
    """
    params: list = []
    if run_type:
        query += " WHERE r.run_type = ?"
        params.append(run_type)
    query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                r.*, e.groundedness_score, e.relevance_score,
                e.completeness_score, e.clarity_score, e.hallucination_risk,
                e.overall_score, e.method AS eval_method
            FROM experiment_runs r
            LEFT JOIN evaluation_results e ON e.experiment_run_id = r.id
            WHERE r.id = ?
            """,
            (run_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_run(run_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM experiment_runs WHERE id = ?", (run_id,))
        return cur.rowcount > 0


def get_stats() -> dict:
    """Aggregate statistics across all experiment runs."""
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM experiment_runs"
        ).fetchone()["n"]

        avg = conn.execute(
            """
            SELECT
                AVG(e.overall_score)       AS avg_overall,
                AVG(e.groundedness_score)  AS avg_groundedness,
                AVG(e.relevance_score)     AS avg_relevance,
                AVG(e.completeness_score)  AS avg_completeness,
                AVG(e.clarity_score)       AS avg_clarity,
                AVG(e.hallucination_risk)  AS avg_hallucination_risk
            FROM evaluation_results e
            """
        ).fetchone()

        by_template = conn.execute(
            """
            SELECT
                r.prompt_template_name AS template_name,
                COUNT(*)               AS run_count,
                AVG(e.overall_score)   AS avg_score,
                AVG(e.groundedness_score) AS avg_groundedness,
                AVG(e.relevance_score)    AS avg_relevance
            FROM experiment_runs r
            LEFT JOIN evaluation_results e ON e.experiment_run_id = r.id
            WHERE r.prompt_template_name IS NOT NULL
            GROUP BY r.prompt_template_name
            ORDER BY avg_score DESC
            """
        ).fetchall()

        def _r(v: object) -> float:
            return round(float(v), 3) if v is not None else 0.0

        return {
            "total_runs":            total,
            "avg_overall_score":     _r(avg["avg_overall"]),
            "avg_groundedness":      _r(avg["avg_groundedness"]),
            "avg_relevance":         _r(avg["avg_relevance"]),
            "avg_completeness":      _r(avg["avg_completeness"]),
            "avg_clarity":           _r(avg["avg_clarity"]),
            "avg_hallucination_risk":_r(avg["avg_hallucination_risk"]),
            "by_template": [dict(r) for r in by_template],
        }
