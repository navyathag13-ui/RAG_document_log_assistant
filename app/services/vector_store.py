"""
ChromaDB vector store — persistence, upsert, query, and delete.

The collection uses cosine distance so that similarity scores are
intuitive (1 = identical, 0 = unrelated).
"""
from __future__ import annotations

import os
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Initialise ChromaDB client ───────────────────────────────────────────────────

os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)

_client = chromadb.PersistentClient(
    path=settings.CHROMA_DB_PATH,
    settings=ChromaSettings(anonymized_telemetry=False),
)

_collection = _client.get_or_create_collection(
    name=settings.CHROMA_COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)

logger.info(
    "ChromaDB collection '%s' ready (%d chunks).",
    settings.CHROMA_COLLECTION_NAME,
    _collection.count(),
)


# ── Public interface ─────────────────────────────────────────────────────────────

def add_chunks(chunks: list[dict[str, Any]]) -> None:
    """
    Upsert a list of chunk dicts into the collection.

    Each dict must have:
        id        – unique string identifier
        text      – chunk text
        embedding – list[float]
        metadata  – dict with at minimum {doc_id, doc_name, file_type, chunk_index}
    """
    if not chunks:
        return

    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    _collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.info("Upserted %d chunks into collection.", len(chunks))


def query_chunks(
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Return the top-k most similar chunks.

    Each result dict:
        chunk_id, text, score (0–1), metadata
    """
    count = _collection.count()
    if count == 0:
        return []

    n_results = min(top_k, count)
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for chunk_id, text, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # cosine distance ∈ [0, 2]; convert to similarity ∈ [0, 1]
        similarity = round(max(0.0, 1.0 - dist), 4)
        output.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "score": similarity,
                "metadata": meta,
            }
        )
    return output


def get_all_document_metadata() -> list[dict[str, Any]]:
    """
    Return metadata for every chunk (used by GET /documents to build the doc list).
    """
    count = _collection.count()
    if count == 0:
        return []

    results = _collection.get(include=["metadatas"])
    return list(zip(results["ids"], results["metadatas"]))


def delete_document(doc_id: str) -> int:
    """
    Delete all chunks belonging to doc_id.

    Returns the number of chunks deleted.
    """
    results = _collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )
    ids_to_delete = results["ids"]
    if ids_to_delete:
        _collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d chunks for doc_id='%s'.", len(ids_to_delete), doc_id)
    return len(ids_to_delete)


def document_exists(doc_id: str) -> bool:
    results = _collection.get(where={"doc_id": doc_id}, include=[])
    return len(results["ids"]) > 0


def get_all_chunks() -> list[dict[str, Any]]:
    """
    Return every chunk as {id, text, metadata}.

    Used by the hybrid retrieval BM25 index builder.
    Returns an empty list if the collection is empty.
    """
    count = _collection.count()
    if count == 0:
        return []

    results = _collection.get(include=["documents", "metadatas"])
    return [
        {"id": cid, "text": text, "metadata": meta}
        for cid, text, meta in zip(
            results["ids"], results["documents"], results["metadatas"]
        )
    ]


def total_chunks() -> int:
    return _collection.count()
