"""
Evaluation, prompt management, and experiment-tracking API routes.

New endpoints added in v2.0:

  Prompt templates
  ────────────────
  GET  /prompts                  List all templates (built-in + custom)
  POST /prompts                  Create a custom template
  PUT  /prompts/{id}             Update a custom template
  DELETE /prompts/{id}           Delete a custom template

  Comparison
  ──────────
  POST /compare                  Run the same question through ≤4 templates
                                 side-by-side and auto-evaluate each answer.

  Evaluation
  ──────────
  POST /evaluate                 Score any (question, answer, chunks) tuple.

  Experiments
  ───────────
  GET  /experiments              Paginated experiment history
  GET  /experiments/stats        Aggregated stats & per-template leaderboard
  GET  /experiments/{id}         Single run detail
  DELETE /experiments/{id}       Delete one run

  Benchmark
  ─────────
  GET  /benchmark/questions      List the built-in benchmark questions
  POST /benchmark/run            Run all benchmark questions with one template
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    # Prompt templates
    PromptTemplateResponse,
    PromptTemplatesListResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
    # Comparison
    CompareRequest,
    CompareResponse,
    CompareItem,
    # Evaluation
    EvaluateRequest,
    EvaluateResponse,
    # Experiments
    ExperimentRunResponse,
    ExperimentsListResponse,
    ExperimentStatsResponse,
    # Benchmark
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    BenchmarkQuestionResult,
)
from app.services import prompt_service, evaluation_service, experiment_service
from app.services.qa_service import answer_with_template

eval_router = APIRouter(tags=["Evaluation & Experiments"])
logger = logging.getLogger(__name__)

_BENCHMARK_PATH = Path(__file__).parent.parent.parent / "tests" / "benchmark_questions.json"


# ── Prompt templates ──────────────────────────────────────────────────────────

@eval_router.get("/prompts", response_model=PromptTemplatesListResponse)
def list_prompts():
    """List all prompt templates (3 built-in + any custom ones you created)."""
    templates = prompt_service.get_all_templates()
    return PromptTemplatesListResponse(
        total=len(templates),
        templates=[PromptTemplateResponse(**t) for t in templates],
    )


@eval_router.post("/prompts", response_model=PromptTemplateResponse, status_code=201)
def create_prompt(body: CreatePromptRequest):
    """Create a new custom prompt template."""
    tmpl = prompt_service.create_template(
        name=body.name,
        description=body.description or "",
        system_prompt=body.system_prompt,
    )
    return PromptTemplateResponse(**tmpl)


@eval_router.put("/prompts/{template_id}", response_model=PromptTemplateResponse)
def update_prompt(template_id: str, body: UpdatePromptRequest):
    """Update a custom template. Built-in templates cannot be modified."""
    try:
        tmpl = prompt_service.update_template(
            template_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if tmpl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )
    return PromptTemplateResponse(**tmpl)


@eval_router.delete("/prompts/{template_id}", status_code=204)
def delete_prompt(template_id: str):
    """Delete a custom template. Built-in templates cannot be deleted."""
    try:
        deleted = prompt_service.delete_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )


# ── Side-by-side comparison ───────────────────────────────────────────────────

@eval_router.post("/compare", response_model=CompareResponse)
def compare_prompts(body: CompareRequest):
    """
    Run the same question through up to 4 prompt templates simultaneously.

    Each result is auto-evaluated so you can compare groundedness, relevance,
    completeness, clarity, and hallucination risk side-by-side.
    """
    if not body.template_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one template_id in 'template_ids'.",
        )
    if len(body.template_ids) > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 4 templates per comparison request.",
        )

    comparisons: list[CompareItem] = []
    best_id: Optional[str] = None
    best_score: float = -1.0

    for tid in body.template_ids:
        tmpl = prompt_service.get_template(tid)
        if tmpl is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{tid}' not found. Check GET /prompts.",
            )

        try:
            ask_resp, chunks_raw = answer_with_template(
                question=body.question,
                top_k=body.top_k,
                template_id=tid,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        except Exception as exc:
            logger.exception("Error during compare for template '%s'", tid)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            )

        # Evaluate
        eval_scores = evaluation_service.score_answer(
            question=body.question,
            answer=ask_resp.answer,
            chunks=chunks_raw,
        )

        # Persist as experiment run
        run_id = experiment_service.save_run(
            query=body.question,
            answer=ask_resp.answer,
            prompt_template_id=tid,
            prompt_template_name=tmpl["name"],
            top_k=body.top_k,
            llm_used=ask_resp.llm_used,
            retrieval_count=ask_resp.retrieval_count,
            run_type="compare",
        )
        evaluation_service.save_evaluation(run_id, eval_scores)

        if eval_scores["overall_score"] > best_score:
            best_score = eval_scores["overall_score"]
            best_id = tid

        comparisons.append(
            CompareItem(
                template_id=tid,
                template_name=tmpl["name"],
                answer=ask_resp.answer,
                llm_used=ask_resp.llm_used,
                retrieval_count=ask_resp.retrieval_count,
                sources=ask_resp.sources,
                groundedness_score=eval_scores["groundedness_score"],
                relevance_score=eval_scores["relevance_score"],
                completeness_score=eval_scores["completeness_score"],
                clarity_score=eval_scores["clarity_score"],
                hallucination_risk=eval_scores["hallucination_risk"],
                overall_score=eval_scores["overall_score"],
                experiment_run_id=run_id,
            )
        )

    return CompareResponse(
        question=body.question,
        top_k=body.top_k,
        comparisons=comparisons,
        best_template_id=best_id,
    )


# ── Evaluation ────────────────────────────────────────────────────────────────

@eval_router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_answer(body: EvaluateRequest):
    """
    Score any (question, answer, chunks) triple using rule-based evaluation.

    Useful for ad-hoc scoring without triggering a full pipeline run.
    """
    chunks_raw = [c.model_dump() for c in body.chunks]
    scores = evaluation_service.score_answer(
        question=body.question,
        answer=body.answer,
        chunks=chunks_raw,
    )
    return EvaluateResponse(**scores)


# ── Experiments ───────────────────────────────────────────────────────────────

@eval_router.get("/experiments/stats", response_model=ExperimentStatsResponse)
def experiment_stats():
    """Aggregated evaluation statistics and per-template leaderboard."""
    stats = experiment_service.get_stats()
    return ExperimentStatsResponse(**stats)


@eval_router.get("/experiments", response_model=ExperimentsListResponse)
def list_experiments(
    limit: int = 50,
    offset: int = 0,
    run_type: Optional[str] = None,
):
    """
    Paginated list of all experiment runs with their evaluation scores.

    Filter by run_type: 'single' | 'compare' | 'benchmark'
    """
    runs = experiment_service.get_runs(limit=limit, offset=offset, run_type=run_type)
    return ExperimentsListResponse(
        total=len(runs),
        runs=[ExperimentRunResponse(**r) for r in runs],
    )


@eval_router.get("/experiments/{run_id}", response_model=ExperimentRunResponse)
def get_experiment(run_id: str):
    """Get full detail for a single experiment run."""
    run = experiment_service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment run '{run_id}' not found.",
        )
    return ExperimentRunResponse(**run)


@eval_router.delete("/experiments/{run_id}", status_code=204)
def delete_experiment(run_id: str):
    """Delete a single experiment run (cascades to its evaluation record)."""
    deleted = experiment_service.delete_run(run_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment run '{run_id}' not found.",
        )


# ── Benchmark ─────────────────────────────────────────────────────────────────

@eval_router.get("/benchmark/questions")
def list_benchmark_questions():
    """Return the built-in set of 15 engineering benchmark questions."""
    if not _BENCHMARK_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="benchmark_questions.json not found in tests/.",
        )
    with open(_BENCHMARK_PATH) as f:
        data = json.load(f)
    return data


@eval_router.post("/benchmark/run", response_model=BenchmarkRunResponse)
def run_benchmark(body: BenchmarkRunRequest):
    """
    Run all benchmark questions against one prompt template and evaluate each answer.

    Results are saved as 'benchmark' experiment runs for historical comparison.
    """
    # Validate template
    tmpl = prompt_service.get_template(body.template_id)
    if tmpl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{body.template_id}' not found.",
        )

    # Load questions
    if not _BENCHMARK_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="benchmark_questions.json not found in tests/.",
        )
    with open(_BENCHMARK_PATH) as f:
        bq_data = json.load(f)

    questions = bq_data["questions"]
    results: list[BenchmarkQuestionResult] = []
    total_overall = 0.0

    for bq in questions:
        question_text = bq["question"]
        try:
            ask_resp, chunks_raw = answer_with_template(
                question=question_text,
                top_k=body.top_k,
                template_id=body.template_id,
            )
        except ValueError:
            # No documents indexed — stop early
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents indexed. Ingest documents before running benchmark.",
            )
        except Exception as exc:
            logger.warning("Benchmark Q '%s' failed: %s", bq["id"], exc)
            continue

        eval_scores = evaluation_service.score_answer(
            question=question_text,
            answer=ask_resp.answer,
            chunks=chunks_raw,
        )

        run_id = experiment_service.save_run(
            query=question_text,
            answer=ask_resp.answer,
            prompt_template_id=body.template_id,
            prompt_template_name=tmpl["name"],
            top_k=body.top_k,
            llm_used=ask_resp.llm_used,
            retrieval_count=ask_resp.retrieval_count,
            run_type="benchmark",
        )
        evaluation_service.save_evaluation(run_id, eval_scores)
        total_overall += eval_scores["overall_score"]

        results.append(
            BenchmarkQuestionResult(
                question_id=bq["id"],
                question=question_text,
                category=bq.get("category", ""),
                difficulty=bq.get("difficulty", ""),
                answer=ask_resp.answer,
                overall_score=eval_scores["overall_score"],
                groundedness_score=eval_scores["groundedness_score"],
                relevance_score=eval_scores["relevance_score"],
                experiment_run_id=run_id,
            )
        )

    avg_score = round(total_overall / len(results), 3) if results else 0.0

    return BenchmarkRunResponse(
        template_id=body.template_id,
        template_name=tmpl["name"],
        top_k=body.top_k,
        total_questions=len(results),
        avg_overall_score=avg_score,
        results=results,
    )
