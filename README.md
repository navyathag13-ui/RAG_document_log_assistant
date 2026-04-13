# Engineering Document & Log Assistant (RAG)

A production-style **retrieval-augmented generation (RAG)** backend that answers engineering questions grounded in real source documents — manuals, troubleshooting guides, system logs, and internal notes.

Built with **FastAPI**, **ChromaDB**, and **sentence-transformers**. LLM synthesis is optional: the full retrieval pipeline works without any API key.

---

## What it does

| Capability | Detail |
|---|---|
| Document ingestion | `.txt`, `.md`, `.log`, `.pdf` — chunked, embedded, and stored |
| Semantic search | Cosine-similarity retrieval over a local vector database |
| Grounded QA | Answers generated strictly from retrieved content |
| Source traceability | Every answer links back to the exact chunks and documents used |
| LLM-optional design | Works offline; add an OpenAI key for prose synthesis |

---

## Architecture

```
Request
  │
  ▼
FastAPI  ─── /ingest ──────► FileLoader → TextSplitter → EmbeddingService → VectorStore (ChromaDB)
         ─── /search ──────► EmbeddingService → VectorStore.query → ChunkResults
         ─── /ask ─────────► RetrievalService → QAService (LLM or fallback) → AskResponse
         ─── /documents ───► VectorStore.get_all_metadata → DocumentList
         ─── /health ──────► stats
```

### Key components

| File | Responsibility |
|---|---|
| `app/services/embedding_service.py` | Loads `all-MiniLM-L6-v2` once; generates embeddings |
| `app/services/vector_store.py` | ChromaDB wrapper — upsert, query, delete |
| `app/services/ingest_service.py` | Orchestrates load → chunk → embed → store |
| `app/services/retrieval_service.py` | Embeds query, retrieves top-k chunks |
| `app/services/qa_service.py` | LLM synthesis or formatted retrieval fallback |
| `app/utils/file_loader.py` | Extracts text from .txt/.md/.log/.pdf |
| `app/utils/text_splitter.py` | Paragraph-aware chunking with overlap |

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- ~500 MB disk space (embedding model ~90 MB, downloaded automatically on first run)

### Mac / Linux

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file (LLM key is optional)
cp .env.example .env
# Optional: open .env and add OPENAI_API_KEY=sk-...

# 4. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Windows PowerShell

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file
Copy-Item .env.example .env
# Optional: edit .env and add OPENAI_API_KEY=sk-...

# 4. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at **http://127.0.0.1:8000**
Interactive docs: **http://127.0.0.1:8000/docs**

> **Note on first run:** The embedding model (`all-MiniLM-L6-v2`, ~90 MB) is downloaded automatically from Hugging Face and cached locally. The initial startup takes 30–60 seconds depending on network speed.

---

## API Reference

### `GET /health`

Returns system status and collection statistics.

```bash
curl http://127.0.0.1:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "indexed_documents": 4,
  "total_chunks": 52,
  "llm_available": false
}
```

---

### `POST /ingest`

Upload and index a document. Use `multipart/form-data` with field name `file`.

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -F "file=@data/sample_docs/manual.txt"
```

```bash
# Ingest all four sample documents
for f in data/sample_docs/*; do
  curl -s -X POST http://127.0.0.1:8000/ingest -F "file=@$f" | python3 -m json.tool
done
```

**Response:**
```json
{
  "message": "Successfully ingested 'manual.txt'.",
  "doc_id": "manual_txt_a1b2c3",
  "file_type": "txt",
  "chunks_created": 18
}
```

---

### `GET /documents`

List all indexed documents.

```bash
curl http://127.0.0.1:8000/documents
```

**Response:**
```json
{
  "total_documents": 4,
  "total_chunks": 52,
  "documents": [
    {
      "doc_id": "manual_txt_a1b2c3",
      "file_type": "txt",
      "chunks": 18,
      "ingested_at": "2024-03-05T09:00:00+00:00",
      "source_path": "/tmp/tmpXXXX.txt"
    }
  ]
}
```

---

### `POST /search`

Semantic chunk retrieval. Returns top-k most relevant chunks with similarity scores.

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "hydraulic pump overheating causes", "top_k": 3}'
```

**Response:**
```json
{
  "query": "hydraulic pump overheating causes",
  "total_results": 3,
  "results": [
    {
      "chunk_id": "troubleshooting_guide_txt_b2c3d4_chunk_1",
      "text": "ISSUE 1: HYDRAULIC PUMP OVERHEATING\n\nSymptom: Fluid temperature exceeds 70°C (WARN-T01) or 80°C (FAULT-T02). Pump may have stopped automatically.\n\nPossible causes and checks:\n\nStep 1 — Verify cooling circuit operation ...",
      "score": 0.9142,
      "doc_name": "troubleshooting_guide.txt",
      "file_type": "txt",
      "chunk_index": 1,
      "source_path": "/tmp/tmpXXXX.txt"
    },
    {
      "chunk_id": "manual_txt_a1b2c3_chunk_5",
      "text": "4.2  Temperature\n  Cold-start minimum: 15°C\n  Normal operating range: 40–55°C\n  High-temperature warning: 70°C → SCU generates WARN-T01\n  High-temperature alarm: 80°C → SCU generates FAULT-T02, pump stops automatically",
      "score": 0.8731,
      "doc_name": "manual.txt",
      "file_type": "txt",
      "chunk_index": 5,
      "source_path": "/tmp/tmpXXXX.txt"
    }
  ]
}
```

---

### `POST /ask`

Grounded question answering. Returns a synthesised answer (LLM mode) or formatted excerpts (fallback mode) plus full source attribution.

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What should I check if the hydraulic pump overheats?", "top_k": 5}'
```

**Response (LLM mode, with OPENAI_API_KEY):**
```json
{
  "question": "What should I check if the hydraulic pump overheats?",
  "answer": "According to the troubleshooting guide, if the hydraulic pump overheats you should: (1) Verify the cooling circuit — check that the heat exchanger fan is running and not fuse-blown, confirm cooling water valves are open, and clean any fouled fins. (2) Check fluid level and oil grade (required: ISO VG 46). (3) Review pump loading — if operating continuously at 100% displacement, consider reducing duty cycle. (4) After resolving the root cause, allow fluid to cool below 50°C, press FAULT RESET on the SCU-400, and restart using the standard startup procedure.",
  "llm_used": true,
  "retrieval_count": 5,
  "sources": [
    {
      "chunk_id": "troubleshooting_guide_txt_b2c3d4_chunk_1",
      "doc_name": "troubleshooting_guide.txt",
      "file_type": "txt",
      "text_excerpt": "ISSUE 1: HYDRAULIC PUMP OVERHEATING\n\nSymptom: Fluid temperature exceeds 70°C ...",
      "score": 0.9142
    },
    {
      "chunk_id": "sample_log_log_c3d4e5_chunk_4",
      "doc_name": "sample_log.log",
      "file_type": "log",
      "text_excerpt": "2024-03-04 10:08:40 INFO  [MAINT] Root cause identified: heat exchanger cooling fan fuse ...",
      "score": 0.8651
    }
  ]
}
```

**Response (fallback mode, no API key):**
```json
{
  "question": "What should I check if the hydraulic pump overheats?",
  "answer": "⚠️  LLM synthesis is not enabled (no OPENAI_API_KEY configured).\nThe following excerpts were retrieved from the most relevant document sections:\n\n[1] Source: troubleshooting_guide.txt  (relevance: 0.91)\nISSUE 1: HYDRAULIC PUMP OVERHEATING ...",
  "llm_used": false,
  "retrieval_count": 5,
  "sources": [...]
}
```

---

### `DELETE /documents/{doc_id}`

Remove a document and all its chunks from the index. Get the `doc_id` from `GET /documents`.

```bash
curl -X DELETE http://127.0.0.1:8000/documents/manual_txt_a1b2c3
```

**Response:**
```json
{
  "message": "Document 'manual_txt_a1b2c3' removed from index.",
  "doc_id": "manual_txt_a1b2c3",
  "chunks_deleted": 18
}
```

---

## Postman Testing Guide

1. **Import requests** — create a new Postman collection, then add requests for each endpoint above.

2. **Ingest all sample files first:**
   - Method: `POST`, URL: `http://127.0.0.1:8000/ingest`
   - Body tab → `form-data`
   - Key: `file` (type = File), Value: select a file from `data/sample_docs/`
   - Repeat for all four sample documents.

3. **Verify ingestion:**
   - `GET http://127.0.0.1:8000/documents` — confirm 4 documents and ~50 chunks.

4. **Test search:**
   - Method: `POST`, URL: `http://127.0.0.1:8000/search`
   - Body tab → `raw` → `JSON`
   - Body: `{"query": "voltage calibration thresholds", "top_k": 3}`

5. **Test QA:**
   - Method: `POST`, URL: `http://127.0.0.1:8000/ask`
   - Body: `{"question": "What are the restart steps after a sensor communication fault?", "top_k": 5}`

6. **More sample queries** are in `tests/sample_queries.json`.

---

## Configuration

All settings are controlled via `.env`. Copy `.env.example` to `.env` to get started.

| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model name |
| `CHUNK_SIZE` | `500` | Max characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap characters between chunks |
| `DEFAULT_TOP_K` | `5` | Default number of retrieved chunks |
| `OPENAI_API_KEY` | _(empty)_ | Required for LLM synthesis; leave blank for fallback mode |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Model used for answer generation |
| `CHROMA_DB_PATH` | `data/chroma_db` | Where ChromaDB persists the vector index |

---

## Offline / No API Key Mode

The retrieval pipeline is **fully functional without any API key**:
- `/ingest`, `/search`, `/documents`, `/delete` work exactly the same.
- `/ask` returns the top retrieved chunks formatted as a structured response, clearly labelled as retrieval-only output.

This makes the project runnable as a complete demo without any cloud dependency.

---

## Error Handling

| Scenario | HTTP Status | Behaviour |
|---|---|---|
| Unsupported file type | `415` | Error with accepted types listed |
| Empty or unreadable file | `422` | Error with file name and reason |
| PDF extraction failure | `500` | Error with extraction details |
| No documents indexed | `404` | Prompt to ingest documents first |
| Document not found (DELETE) | `404` | Error with valid ID hint |

---

## Project Structure

```
engineering-rag-assistant/
├── app/
│   ├── main.py                   # FastAPI app, lifespan, middleware
│   ├── api/routes.py             # All endpoint handlers
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   └── logging_config.py     # Structured logging setup
│   ├── models/schemas.py         # Request/response Pydantic models
│   ├── services/
│   │   ├── embedding_service.py  # sentence-transformers singleton
│   │   ├── vector_store.py       # ChromaDB wrapper
│   │   ├── ingest_service.py     # Ingestion pipeline
│   │   ├── retrieval_service.py  # Query → top-k chunks
│   │   └── qa_service.py         # LLM or fallback answer generation
│   └── utils/
│       ├── file_loader.py        # .txt / .md / .log / .pdf loaders
│       └── text_splitter.py      # Paragraph-aware chunker
├── data/
│   └── sample_docs/              # Ready-to-ingest engineering documents
├── tests/
│   └── sample_queries.json       # Sample API requests for all endpoints
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework and automatic OpenAPI docs |
| `uvicorn` | ASGI server |
| `chromadb` | Local persistent vector database |
| `sentence-transformers` | Local embedding model (no API key needed) |
| `pypdf` | PDF text extraction |
| `openai` | LLM synthesis (optional) |
| `pydantic-settings` | Typed configuration from `.env` |
| `python-multipart` | File upload support |

---

## License

MIT — free to use, modify, and include in your portfolio.
