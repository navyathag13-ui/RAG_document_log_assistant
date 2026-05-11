"""
Retrieval service: embed the query and fetch the top-k matching chunks.

Two retrieval modes:

  semantic  — pure cosine-similarity search via ChromaDB HNSW (default)
  hybrid    — combines semantic scores with BM25 keyword scores, then
              re-ranks by a weighted combination.
              Requires the `rank-bm25` package (included in requirements.txt).
              Falls back to semantic-only if the package is missing.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import ChunkResult
from app.services import embedding_service, vector_store

logger = get_logger(__name__)


# ── Semantic retrieval (original, unchanged) ──────────────────────────────────

def retrieve(
    query: str,
    top_k: Optional[int] = None,
    use_hybrid: bool = False,
    hybrid_alpha: float = 0.7,
) -> list[ChunkResult]:
    """
    Retrieve the top-k most relevant chunks for *query*.

    Parameters
    ----------
    query        : the user's natural-language query or question
    top_k        : number of chunks to return (default: settings.DEFAULT_TOP_K)
    use_hybrid   : if True, blend semantic + BM25 scores
    hybrid_alpha : weight for semantic component (1.0 = pure semantic)

    Raises
    ------
    ValueError : if no documents have been indexed yet.
    """
    top_k = top_k or settings.DEFAULT_TOP_K

    if vector_store.total_chunks() == 0:
        raise ValueError(
            "No documents have been indexed yet. Ingest documents first via POST /ingest."
        )

    if use_hybrid:
        return _retrieve_hybrid(query, top_k=top_k, alpha=hybrid_alpha)

    logger.info("Semantic retrieval top-%d for: '%s'", top_k, query[:80])

    query_embedding = embedding_service.embed_query(query)
    raw_results = vector_store.query_chunks(query_embedding, top_k=top_k)

    results = _to_chunk_results(raw_results)
    logger.info(
        "Retrieved %d chunks (top score=%.4f).",
        len(results),
        results[0].score if results else 0.0,
    )
    return results


# ── Hybrid retrieval (BM25 + semantic) ────────────────────────────────────────

def _retrieve_hybrid(
    query: str,
    top_k: int,
    alpha: float,
) -> list[ChunkResult]:
    """
    Blend semantic cosine similarity with BM25 keyword matching.

    Strategy
    --------
    1. Fetch semantic top-(top_k × 3) candidates from ChromaDB.
    2. Build a BM25Okapi index on ALL indexed chunks (fast for small corpora).
    3. Normalize both score sets to [0, 1].
    4. Combined score = alpha × semantic + (1 − alpha) × bm25.
    5. Return the top-k chunks by combined score.
    """
    logger.info(
        "Hybrid retrieval top-%d (alpha=%.2f) for: '%s'", top_k, alpha, query[:80]
    )

    # Step 1 — semantic candidates
    query_embedding = embedding_service.embed_query(query)
    n_semantic = min(top_k * 3, vector_store.total_chunks())
    semantic_raw = vector_store.query_chunks(query_embedding, top_k=n_semantic)
    semantic_scores: dict[str, float] = {r["chunk_id"]: r["score"] for r in semantic_raw}

    # Step 2 — BM25 index over all chunks
    all_chunks = vector_store.get_all_chunks()
    if not all_chunks:
        return retrieve(query, top_k=top_k)   # defensive fallback

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning(
            "rank-bm25 not installed; falling back to semantic search. "
            "Run: pip install rank-bm25"
        )
        return retrieve(query, top_k=top_k)

    ids       = [c["id"]       for c in all_chunks]
    texts     = [c["text"]     for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    corpus   = [t.lower().split() for t in texts]
    bm25_idx = BM25Okapi(corpus)
    bm25_raw = bm25_idx.get_scores(query.lower().split())

    # Step 3 — normalize BM25 to [0, 1]
    max_bm25 = max(bm25_raw) if max(bm25_raw) > 0 else 1.0
    bm25_scores: dict[str, float] = {
        ids[i]: float(bm25_raw[i]) / max_bm25 for i in range(len(ids))
    }

    # Step 4 — merge; consider chunks that appear in either source
    candidate_ids = set(semantic_scores) | {
        ids[i] for i in range(len(ids)) if bm25_raw[i] > 0
    }

    semantic_lookup = {r["chunk_id"]: r for r in semantic_raw}

    merged: list[dict] = []
    for cid in candidate_ids:
        sem  = semantic_scores.get(cid, 0.0)
        bm25 = bm25_scores.get(cid, 0.0)
        combined = alpha * sem + (1.0 - alpha) * bm25

        if cid in semantic_lookup:
            raw = semantic_lookup[cid]
            chunk_text = raw["text"]
            meta       = raw["metadata"]
        else:
            idx        = ids.index(cid)
            chunk_text = texts[idx]
            meta       = metadatas[idx]

        merged.append(
            {
                "chunk_id": cid,
                "text":     chunk_text,
                "score":    round(combined, 4),
                "metadata": meta,
            }
        )

    # Step 5 — sort and truncate
    merged.sort(key=lambda x: x["score"], reverse=True)
    top = merged[:top_k]

    results = _to_chunk_results(top)
    logger.info(
        "Hybrid retrieved %d chunks (top score=%.4f).",
        len(results),
        results[0].score if results else 0.0,
    )
    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_chunk_results(raw: list[dict]) -> list[ChunkResult]:
    out: list[ChunkResult] = []
    for r in raw:
        meta = r["metadata"]
        out.append(
            ChunkResult(
                chunk_id    = r["chunk_id"],
                text        = r["text"],
                score       = r["score"],
                doc_name    = meta.get("doc_name",    "unknown"),
                file_type   = meta.get("file_type",   "unknown"),
                chunk_index = meta.get("chunk_index", 0),
                source_path = meta.get("source_path"),
            )
        )
    return out
