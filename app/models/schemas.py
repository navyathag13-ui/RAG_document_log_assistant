"""
Pydantic request / response schemas for all API endpoints (v2).

v1 schemas are preserved unchanged so all existing endpoints keep working.
v2 schemas extend the API with prompt management, comparison, evaluation,
and experiment tracking.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# v1 — Existing schemas (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    indexed_documents: int
    total_chunks: int
    llm_available: bool


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    message: str
    doc_id: str
    file_type: str
    chunks_created: int


# ── Documents list ────────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    doc_id: str
    file_type: str
    chunks: int
    ingested_at: str | None = None
    source_path: str | None = None


class DocumentsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    documents: list[DocumentInfo]


# ── Search ────────────────────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to return")
    # v2 optional: enable BM25 + semantic hybrid retrieval
    use_hybrid: bool = Field(default=False, description="Use hybrid BM25 + semantic retrieval")
    hybrid_alpha: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Blend: 1.0 = pure semantic, 0.0 = pure BM25"
    )


class ChunkResult(BaseModel):
    chunk_id: str
    text: str
    score: float = Field(description="Similarity score 0–1; higher is more relevant")
    doc_name: str
    file_type: str
    chunk_index: int
    source_path: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkResult]
    total_results: int
    retrieval_mode: str = "semantic"   # "semantic" | "hybrid"


# ── Ask / QA ──────────────────────────────────────────────────────────────────

class AskQuery(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve")
    # v2 optional: select a prompt template and request evaluation
    template_id: Optional[str] = Field(
        default=None,
        description="Prompt template ID (see GET /prompts). Defaults to 'technical'."
    )
    auto_evaluate: bool = Field(
        default=True,
        description="Automatically score the answer after generation."
    )


class SourceChunk(BaseModel):
    chunk_id: str
    doc_name: str
    file_type: str
    text_excerpt: str = Field(description="First 300 characters of the chunk")
    score: float


class EvalScores(BaseModel):
    """Inline evaluation scores returned alongside a generated answer."""
    groundedness_score: float
    relevance_score: float
    completeness_score: float
    clarity_score: float
    hallucination_risk: float
    overall_score: float
    method: str = "rule_based"


class AskResponse(BaseModel):
    question: str
    answer: str
    llm_used: bool = Field(description="True when answer was synthesised by an LLM")
    retrieval_count: int
    sources: list[SourceChunk]
    # v2 optional enrichments
    evaluation: Optional[EvalScores] = None
    experiment_run_id: Optional[str] = None
    template_name: Optional[str] = None


# ── Delete ────────────────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    message: str
    doc_id: str
    chunks_deleted: int


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    context: dict[str, Any] | None = None


# ══════════════════════════════════════════════════════════════════════════════
# v2 — New schemas
# ══════════════════════════════════════════════════════════════════════════════

# ── Prompt templates ──────────────────────────────────────────────────────────

class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    system_prompt: str
    is_builtin: int = 0
    created_at: str
    updated_at: str


class PromptTemplatesListResponse(BaseModel):
    total: int
    templates: list[PromptTemplateResponse]


class CreatePromptRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=200)
    system_prompt: str = Field(..., min_length=10)


class UpdatePromptRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=200)
    system_prompt: Optional[str] = None


# ── Side-by-side comparison ───────────────────────────────────────────────────

class CompareRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    template_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="List of 1–4 template IDs to compare (e.g. ['technical','detailed','concise'])",
    )


class CompareItem(BaseModel):
    template_id: str
    template_name: str
    answer: str
    llm_used: bool
    retrieval_count: int
    sources: list[SourceChunk]
    groundedness_score: float
    relevance_score: float
    completeness_score: float
    clarity_score: float
    hallucination_risk: float
    overall_score: float
    experiment_run_id: str


class CompareResponse(BaseModel):
    question: str
    top_k: int
    comparisons: list[CompareItem]
    best_template_id: Optional[str] = None


# ── Evaluation ────────────────────────────────────────────────────────────────

class EvalChunk(BaseModel):
    """Minimal chunk representation used in the /evaluate endpoint."""
    text: str
    score: float
    doc_name: Optional[str] = None


class EvaluateRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    chunks: list[EvalChunk] = Field(..., min_length=1)


class EvaluateResponse(BaseModel):
    groundedness_score: float
    relevance_score: float
    completeness_score: float
    clarity_score: float
    hallucination_risk: float
    overall_score: float
    method: str
    details: Optional[dict] = None


# ── Experiments ───────────────────────────────────────────────────────────────

class ExperimentRunResponse(BaseModel):
    id: str
    query: str
    prompt_template_id: Optional[str] = None
    prompt_template_name: Optional[str] = None
    top_k: int
    answer: str
    llm_used: int
    retrieval_count: int
    run_type: str
    created_at: str
    # Joined evaluation fields (may be None if not evaluated)
    groundedness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    completeness_score: Optional[float] = None
    clarity_score: Optional[float] = None
    hallucination_risk: Optional[float] = None
    overall_score: Optional[float] = None
    eval_method: Optional[str] = None


class ExperimentsListResponse(BaseModel):
    total: int
    runs: list[ExperimentRunResponse]


class TemplateLeaderboardEntry(BaseModel):
    template_name: str
    run_count: int
    avg_score: Optional[float] = None
    avg_groundedness: Optional[float] = None
    avg_relevance: Optional[float] = None


class ExperimentStatsResponse(BaseModel):
    total_runs: int
    avg_overall_score: float
    avg_groundedness: float
    avg_relevance: float
    avg_completeness: float
    avg_clarity: float
    avg_hallucination_risk: float
    by_template: list[dict]


# ── Benchmark ─────────────────────────────────────────────────────────────────

class BenchmarkRunRequest(BaseModel):
    template_id: str = Field(default="technical", description="Prompt template to benchmark")
    top_k: int = Field(default=5, ge=1, le=20)


class BenchmarkQuestionResult(BaseModel):
    question_id: str
    question: str
    category: str
    difficulty: str
    answer: str
    overall_score: float
    groundedness_score: float
    relevance_score: float
    experiment_run_id: str


class BenchmarkRunResponse(BaseModel):
    template_id: str
    template_name: str
    top_k: int
    total_questions: int
    avg_overall_score: float
    results: list[BenchmarkQuestionResult]
