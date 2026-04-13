"""
Ingest pipeline: load → clean → chunk → embed → store.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.core.logging_config import get_logger
from app.services import embedding_service, vector_store
from app.utils.file_loader import load_file
from app.utils.text_splitter import split_text

logger = get_logger(__name__)


def ingest_file(file_path: str | Path, original_filename: str | None = None) -> dict:
    """
    Ingest a single file into the vector store.

    Returns a summary dict:
        doc_id, file_type, chunks_created, already_existed
    """
    path = Path(file_path)
    filename = original_filename or path.name

    # Stable doc_id derived from filename (safe for use as a query filter)
    doc_id = _make_doc_id(filename)

    # ── Load & chunk ────────────────────────────────────────────────────────────
    raw_text, file_type = load_file(path)
    chunks = split_text(raw_text)

    if not chunks:
        raise ValueError(f"No usable text chunks produced from '{filename}'.")

    logger.info("Ingesting '%s': %d chunks to embed.", filename, len(chunks))

    # ── Embed ────────────────────────────────────────────────────────────────────
    embeddings = embedding_service.embed_texts(chunks)

    # ── Build records ────────────────────────────────────────────────────────────
    ingested_at = datetime.now(timezone.utc).isoformat()
    records = []
    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{doc_id}_chunk_{idx}"
        records.append(
            {
                "id": chunk_id,
                "text": chunk_text,
                "embedding": embedding,
                "metadata": {
                    "doc_id": doc_id,
                    "doc_name": filename,
                    "file_type": file_type,
                    "chunk_index": idx,
                    "source_path": str(path),
                    "ingested_at": ingested_at,
                },
            }
        )

    # ── Store ────────────────────────────────────────────────────────────────────
    vector_store.add_chunks(records)
    logger.info("Successfully ingested '%s' (%d chunks, doc_id=%s).", filename, len(records), doc_id)

    return {
        "doc_id": doc_id,
        "file_type": file_type,
        "chunks_created": len(records),
    }


def _make_doc_id(filename: str) -> str:
    """
    Create a stable, filesystem-safe doc_id from a filename.

    We keep the original filename but append a short hash to avoid collisions
    if two files share the same base name.
    Example: "manual.txt" → "manual_txt_a1b2c3"
    """
    stem = Path(filename).stem
    ext = Path(filename).suffix.lstrip(".")
    short_hash = hashlib.md5(filename.encode()).hexdigest()[:6]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{stem}_{ext}")
    return f"{safe}_{short_hash}"
