# Engineering RAG Assistant -- container image for Azure Container Apps.
#
# Single-stage build: sentence-transformers/torch/chromadb pull in enough
# native dependencies, and this image runs as a long-lived API server (not
# a build artifact someone extracts files from), that a multi-stage split
# wasn't worth the added complexity for a project this size. A production
# deployment at real scale would want one, to shrink the final image --
# see README "Demo-scale vs production-scale".
#
# The embedding model is downloaded at BUILD time (not on first request)
# so a fresh container starts ready to serve immediately and doesn't need
# outbound network access to Hugging Face at runtime -- only to whichever
# LLM / Content Safety endpoints are configured, if any.
#
# Verified: a build from a clean git clone succeeded and the container served /health, /ingest,
# /search and /ask (Apple silicon, docker 29.8.0). Not verified: amd64, Azure Container Apps.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# build-essential is needed for a couple of wheels to compile; removed
# again in the same layer so it doesn't end up in the final image. curl
# stays -- it's used by HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app/ ./app/
COPY data/sample_docs/ ./data/sample_docs/

# Azure Container Apps' default container security context expects a
# non-root process; make that explicit rather than relying on the
# platform to enforce it.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data/chroma_db \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# IMPORTANT: ChromaDB (data/chroma_db) and the experiments SQLite DB
# (data/experiments.db) are written inside the container filesystem.
# Without a mounted volume, both are lost on every container restart or
# new revision -- fine for a demo, not fine for anything real. See
# README "Deployment" for the optional Azure Files mount that fixes this.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
