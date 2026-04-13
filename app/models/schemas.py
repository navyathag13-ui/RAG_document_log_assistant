"""
Pydantic request / response schemas for all API endpoints.
"""
from typing import Any
from pydantic import BaseModel, Field


# ── Health ───────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    indexed_documents: int
    total_chunks: int
    llm_available: bool


# ── Ingest ───────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    message: str
    doc_id: str
    file_type: str
    chunks_created: int


# ── Documents list ────────────────────────────────────────────────────────────────

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


# ── Search ───────────────────────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to return")


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


# ── Ask / QA ─────────────────────────────────────────────────────────────────────

class AskQuery(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve")


class SourceChunk(BaseModel):
    chunk_id: str
    doc_name: str
    file_type: str
    text_excerpt: str = Field(description="First 300 characters of the chunk")
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    llm_used: bool = Field(description="True when answer was synthesised by an LLM")
    retrieval_count: int
    sources: list[SourceChunk]


# ── Delete ────────────────────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    message: str
    doc_id: str
    chunks_deleted: int


# ── Error ─────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    context: dict[str, Any] | None = None
