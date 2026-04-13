"""
Retrieval service: embed the query and fetch the top-k matching chunks.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import ChunkResult
from app.services import embedding_service, vector_store

logger = get_logger(__name__)


def retrieve(query: str, top_k: int | None = None) -> list[ChunkResult]:
    """
    Embed *query* and return the top-k most relevant chunks as ChunkResult objects.

    Raises:
        ValueError: if the vector store is empty.
    """
    top_k = top_k or settings.DEFAULT_TOP_K

    if vector_store.total_chunks() == 0:
        raise ValueError(
            "No documents have been indexed yet. Ingest documents first via POST /ingest."
        )

    logger.info("Retrieving top-%d chunks for query: '%s'", top_k, query[:80])

    query_embedding = embedding_service.embed_query(query)
    raw_results = vector_store.query_chunks(query_embedding, top_k=top_k)

    results: list[ChunkResult] = []
    for r in raw_results:
        meta = r["metadata"]
        results.append(
            ChunkResult(
                chunk_id=r["chunk_id"],
                text=r["text"],
                score=r["score"],
                doc_name=meta.get("doc_name", "unknown"),
                file_type=meta.get("file_type", "unknown"),
                chunk_index=meta.get("chunk_index", 0),
                source_path=meta.get("source_path"),
            )
        )

    logger.info("Retrieved %d chunks (top score=%.4f).", len(results), results[0].score if results else 0.0)
    return results
