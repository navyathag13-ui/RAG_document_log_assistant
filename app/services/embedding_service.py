"""
Singleton wrapper around a sentence-transformers embedding model.

The model is loaded once at application startup and reused for all requests.
Default: all-MiniLM-L6-v2  (~90 MB download on first use, then cached locally).
"""
from __future__ import annotations

import threading

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_model = None
_lock = threading.Lock()


def get_model():
    """Return the (lazily loaded) sentence-transformers model."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _load_model()
    return _model


def _load_model() -> None:
    global _model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is required. Install: pip install sentence-transformers"
        )
    logger.info("Loading embedding model '%s' …", settings.EMBEDDING_MODEL)
    _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info("Embedding model ready.")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of strings.

    Returns a list of float vectors (one per input text).
    """
    if not texts:
        return []
    model = get_model()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    """Convenience wrapper: embed a single query string."""
    return embed_texts([query])[0]
