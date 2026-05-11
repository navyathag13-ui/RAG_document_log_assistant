"""
Rule-based answer evaluation service.

Scores answers on five dimensions without requiring an LLM or external API:

  1. Groundedness    — How much of the answer is supported by retrieved context.
  2. Relevance       — Average semantic similarity score of the retrieved chunks.
  3. Completeness    — Does the answer fully address the question's apparent scope.
  4. Clarity         — Is the answer well-structured with good sentence rhythm.
  5. Hallucination Risk — Presence of specific technical claims not found in context.

Each dimension is normalised to [0.0, 1.0].  Higher is always better,
except Hallucination Risk where a lower score is safer (displayed as-is
with a note that 0 = no risk).

The weighted Overall score is:
    0.30 × groundedness + 0.25 × relevance + 0.20 × completeness
  + 0.15 × clarity     + 0.10 × (1 − hallucination_risk)
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from app.db.database import get_db

logger = logging.getLogger(__name__)


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_answer(
    question: str,
    answer: str,
    chunks: list[dict],   # each dict: {text, score, doc_name, ...}
) -> dict:
    """
    Score an answer against the retrieved context.

    Parameters
    ----------
    question : the original user question
    answer   : the generated or formatted answer text
    chunks   : the retrieved chunks used (each must have 'text' and 'score')

    Returns a dict with six numeric fields and a 'details' sub-dict.
    """
    answer_lower = answer.lower()
    all_context = " ".join(c.get("text", "") for c in chunks)
    all_context_lower = all_context.lower()
    context_words = set(re.findall(r"\b\w{4,}\b", all_context_lower))

    # ── 1. Relevance ─────────────────────────────────────────────────────────
    scores = [float(c.get("score", 0.0)) for c in chunks]
    relevance = round(mean(scores), 4) if scores else 0.0

    # ── 2. Groundedness ──────────────────────────────────────────────────────
    # Fraction of "meaningful" answer words (≥5 chars) found in context.
    answer_words = set(re.findall(r"\b\w{5,}\b", answer_lower))
    if answer_words:
        grounded_count = len(answer_words & context_words)
        raw_groundedness = grounded_count / len(answer_words)
        # Slight normalisation: a score of 0.6 raw maps to ~0.9 grounded
        groundedness = round(min(1.0, raw_groundedness * 1.4), 4)
    else:
        groundedness = 0.0

    # Penalise answers that explicitly admit no information was found
    no_info_phrases = [
        "does not contain", "not available", "no information",
        "cannot answer", "insufficient", "not found in",
    ]
    if any(p in answer_lower for p in no_info_phrases):
        groundedness = round(min(groundedness, 0.35), 4)

    # ── 3. Completeness ───────────────────────────────────────────────────────
    q_words = len(question.split())
    a_words = len(answer.split())

    expected_min  = max(15, q_words * 3)
    expected_good = max(60, q_words * 8)

    if a_words >= expected_good:
        completeness = 1.0
    elif a_words >= expected_min:
        completeness = 0.5 + 0.5 * (a_words - expected_min) / max(1, expected_good - expected_min)
    else:
        completeness = a_words / max(1, expected_min)
    completeness = round(completeness, 4)

    # ── 4. Clarity ────────────────────────────────────────────────────────────
    sentences = [s.strip() for s in re.split(r"[.!?]+", answer) if s.strip()]
    if not sentences:
        clarity = 0.3
    else:
        avg_len = a_words / len(sentences)
        if 10 <= avg_len <= 25:
            clarity = 1.0
        elif avg_len < 5:
            clarity = 0.4
        elif avg_len > 45:
            clarity = 0.45
        else:
            clarity = 0.70
        # Small bonus for structured answers (numbered/bulleted lists)
        if re.search(r"(\d+\.|[-•*])\s", answer):
            clarity = min(1.0, clarity + 0.10)
    clarity = round(clarity, 4)

    # ── 5. Hallucination Risk ────────────────────────────────────────────────
    # Check for CamelCase/ALL-CAPS technical terms and numeric measurements
    # that appear in the answer but NOT in the retrieved context.
    tech_terms_in_answer = set(re.findall(r"\b[A-Z][A-Za-z0-9-]{3,}\b", answer))
    measurements_in_answer = set(
        re.findall(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:bar|psi|°[CF]|rpm|vdc|v|hz|l/min|lpm|kg|kw|w|a|°f)\b",
            answer_lower,
        )
    )

    risky_terms = [t for t in tech_terms_in_answer if t not in all_context]
    risky_nums  = [n for n in measurements_in_answer if n not in all_context_lower]

    total_specific = len(tech_terms_in_answer) + len(measurements_in_answer)
    if total_specific > 0:
        hallucination_risk = round(
            min(1.0, (len(risky_terms) + len(risky_nums)) / total_specific), 4
        )
    else:
        hallucination_risk = 0.05   # near-zero when no specific claims made

    # ── Overall (weighted) ───────────────────────────────────────────────────
    overall = round(
        0.30 * groundedness
        + 0.25 * relevance
        + 0.20 * completeness
        + 0.15 * clarity
        + 0.10 * (1.0 - hallucination_risk),
        4,
    )

    details = {
        "answer_word_count": a_words,
        "sentence_count": len(sentences),
        "grounded_word_count": len(answer_words & context_words) if answer_words else 0,
        "risky_technical_terms": list(risky_terms)[:6],
        "chunk_count": len(chunks),
    }

    return {
        "groundedness_score":  groundedness,
        "relevance_score":     relevance,
        "completeness_score":  completeness,
        "clarity_score":       clarity,
        "hallucination_risk":  hallucination_risk,
        "overall_score":       overall,
        "method":              "rule_based",
        "details":             details,
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def save_evaluation(experiment_run_id: str, scores: dict) -> str:
    """Persist evaluation scores linked to an experiment run. Returns eval ID."""
    eval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO evaluation_results
                (id, experiment_run_id, groundedness_score, relevance_score,
                 completeness_score, clarity_score, hallucination_risk,
                 overall_score, method, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                experiment_run_id,
                scores["groundedness_score"],
                scores["relevance_score"],
                scores["completeness_score"],
                scores["clarity_score"],
                scores["hallucination_risk"],
                scores["overall_score"],
                scores["method"],
                json.dumps(scores.get("details", {})),
                now,
            ),
        )

    logger.debug("Saved evaluation %s for run %s", eval_id, experiment_run_id)
    return eval_id
