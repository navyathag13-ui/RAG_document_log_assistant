"""
All API route handlers.
"""
from __future__ import annotations

import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import (
    AskQuery,
    AskResponse,
    DeleteResponse,
    DocumentInfo,
    DocumentsResponse,
    HealthResponse,
    IngestResponse,
    SearchQuery,
    SearchResponse,
)
from app.services import ingest_service, qa_service, retrieval_service, vector_store
from app.utils.file_loader import SUPPORTED_EXTENSIONS

router = APIRouter()
logger = get_logger(__name__)

ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-log",
    "application/pdf",
    "application/octet-stream",  # some clients send this as a catch-all
}


# ── Health ───────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Returns service status and collection statistics."""
    # Build doc count from metadata
    meta_pairs = vector_store.get_all_document_metadata()
    unique_docs = {m.get("doc_id") for _, m in meta_pairs}

    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        indexed_documents=len(unique_docs),
        total_chunks=vector_store.total_chunks(),
        llm_available=bool(settings.OPENAI_API_KEY),
    )


# ── Ingest ───────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED, tags=["Ingestion"])
def ingest_document(file: UploadFile = File(...)):
    """
    Upload and ingest a document (.txt, .md, .log, .pdf).

    The file is chunked, embedded, and stored in the vector database.
    Re-ingesting an existing file replaces all its previous chunks.
    """
    # Validate extension
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Save upload to a temp file, then ingest
    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = ingest_service.ingest_file(tmp_path, original_filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return IngestResponse(
        message=f"Successfully ingested '{filename}'.",
        doc_id=result["doc_id"],
        file_type=result["file_type"],
        chunks_created=result["chunks_created"],
    )


# ── Documents list ────────────────────────────────────────────────────────────────

@router.get("/documents", response_model=DocumentsResponse, tags=["Ingestion"])
def list_documents():
    """List all indexed documents with their chunk counts and metadata."""
    meta_pairs = vector_store.get_all_document_metadata()

    # Aggregate by doc_id
    docs: dict[str, dict] = defaultdict(
        lambda: {"chunks": 0, "file_type": "unknown", "ingested_at": None, "source_path": None}
    )
    for _chunk_id, meta in meta_pairs:
        doc_id = meta.get("doc_id", "unknown")
        docs[doc_id]["chunks"] += 1
        docs[doc_id]["file_type"] = meta.get("file_type", "unknown")
        docs[doc_id]["ingested_at"] = meta.get("ingested_at")
        docs[doc_id]["source_path"] = meta.get("source_path")
        docs[doc_id]["doc_name"] = meta.get("doc_name", doc_id)

    doc_list = [
        DocumentInfo(
            doc_id=doc_id,
            file_type=info["file_type"],
            chunks=info["chunks"],
            ingested_at=info["ingested_at"],
            source_path=info["source_path"],
        )
        for doc_id, info in sorted(docs.items())
    ]

    return DocumentsResponse(
        total_documents=len(doc_list),
        total_chunks=vector_store.total_chunks(),
        documents=doc_list,
    )


# ── Search ───────────────────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse, tags=["Retrieval"])
def search(body: SearchQuery):
    """
    Retrieve the top-k most relevant chunks for a query.

    Set use_hybrid=true to blend BM25 keyword matching with semantic similarity.
    hybrid_alpha controls the blend (1.0 = pure semantic, 0.0 = pure BM25).
    """
    try:
        results = retrieval_service.retrieve(
            body.query,
            top_k=body.top_k,
            use_hybrid=body.use_hybrid,
            hybrid_alpha=body.hybrid_alpha,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return SearchResponse(
        query=body.query,
        results=results,
        total_results=len(results),
        retrieval_mode="hybrid" if body.use_hybrid else "semantic",
    )


# ── Ask / QA ─────────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse, tags=["QA"])
def ask(body: AskQuery):
    """
    Grounded question answering over indexed documents.

    Retrieves the most relevant chunks and either:
    - Generates a synthesised answer via LLM (if OPENAI_API_KEY is configured), or
    - Returns a formatted, source-linked answer from the retrieved chunks (fallback).
    """
    try:
        response = qa_service.answer(
            body.question,
            top_k=body.top_k,
            template_id=body.template_id,
            auto_evaluate=body.auto_evaluate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during /ask")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return response


# ── Delete ────────────────────────────────────────────────────────────────────────

@router.delete("/documents/{doc_id}", response_model=DeleteResponse, tags=["Ingestion"])
def delete_document(doc_id: str):
    """Remove all chunks belonging to a document from the vector store."""
    if not vector_store.document_exists(doc_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document found with doc_id='{doc_id}'. Check GET /documents for valid IDs.",
        )

    deleted = vector_store.delete_document(doc_id)
    return DeleteResponse(
        message=f"Document '{doc_id}' removed from index.",
        doc_id=doc_id,
        chunks_deleted=deleted,
    )
