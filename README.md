# Engineering RAG Assistant — Azure-native agentic edition

A retrieval-augmented generation backend for engineering questions, extended into an agentic assistant built on Azure AI Foundry, Azure OpenAI Service, and Semantic Kernel. Started as a FastAPI + ChromaDB + sentence-transformers RAG system with full source attribution and an LLM-optional fallback mode. This edition adds Azure OpenAI as a generation backend alongside that fallback (not instead of it), a Semantic Kernel agent that actually decides which tool to call rather than following a fixed script, and content-safety + groundedness checks that flag problems instead of quietly ignoring them.

Built around the AI-103 (Azure AI Apps and Agents Developer Associate) syllabus. Every result below comes from a real run, and the raw outputs are in `bench/` and `docs/VERIFICATION.md`.

---

## Highlights

- Ask questions of your own manuals and logs and get answers with the exact source passages attached
- An **Azure OpenAI** powered assistant and a **Semantic Kernel agent** that chooses between tools, both run live against real Azure resources
- **Azure AI Content Safety** screening plus a groundedness check on answers
- Still fully usable **offline** with no cloud services at all
- Measured retrieval quality: the right source document at rank 1 for 93.3% of benchmark questions with hybrid search
- An async `/ask` endpoint, benchmarked (roughly 2 to 3 times the throughput offline at 20 concurrent requests)
- A Docker image that builds from a clean clone and serves the API, plus Azure Container Apps deployment scripts and OpenTelemetry monitoring


## Why I built this

If you have ever worked around industrial equipment, you know the routine. Something throws a fault code, and somebody digs through a PDF manual, a folder of service notes and a log file to work out what it means. This project is my attempt at making that faster: you upload the documents, ask a question in plain English, and get an answer with the exact passages it came from. If the documents don't say, it tells you that instead of guessing.

I started with a plain FastAPI and ChromaDB search service, then grew it into something closer to what a team would actually run: Azure OpenAI for the answers, an agent that decides which tool to use, safety checks, Docker, and deployment scripts. Along the way I measured what I built, and some of the results were not what I hoped for. Those are written down below too.

## What's in the box (tech stack)

| Layer | What I used |
|---|---|
| API | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| Retrieval | ChromaDB (vector store), sentence-transformers `all-MiniLM-L6-v2` embeddings, `rank-bm25` for keyword search, hybrid blending of the two |
| Document loading | `pypdf` for PDFs, plus plain text, Markdown and logs |
| Answers | Azure OpenAI (`gpt-4.1-mini` deployment), plain OpenAI as a fallback, and an offline mode that returns the retrieved passages when no model is configured |
| Agent | Semantic Kernel with real function calling (search documents, check equipment status, ask a clarifying question) |
| Safety | Azure AI Content Safety on inputs and outputs, plus a word-overlap groundedness check |
| Telemetry | OpenTelemetry through Azure Monitor / Application Insights |
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS 3, React Query |
| Packaging | Docker (`python:3.11-slim`, embedding model baked into the image), Azure Container Apps scripts in `deploy/` |

## What I measured

Everything here was run on my own laptop (Apple M4, 10 cores, 16 GB). The raw numbers and the scripts are in [`bench/`](bench/), and the day-by-day checks are in [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

| Question | What happened |
|---|---|
| Does the agent make real decisions? | Yes. I ran four live queries and got four different behaviours: a document search, an equipment status check, a clarifying question, and a refusal to make something up. |
| Do the Azure services work live? | Yes. Azure OpenAI (`gpt-4.1-mini`) and Content Safety (free F0 tier) both answered real requests on 2026-09-21. |
| Did making `/ask` async help? | Yes, offline. At 20 concurrent requests the earlier synchronous version handled 27 to 66 requests per second across four runs, and the async version handled 92 to 101. Against the live Azure deployment both versions hit Azure's own rate limit first, so the deployment's capacity tier sets the ceiling there; more capacity is how to go faster. |
| How good is retrieval? | On the 15 built-in questions over the sample documents, the right document is ranked first 86.7% of the time with semantic search alone and 93.3% with the default hybrid search (semantic plus keyword), and it appears in the top 3 every time. Details in [`bench/RESULTS.md`](bench/RESULTS.md). |
| Where is async used? | `/ask` (the LLM and Content Safety calls are awaited) and `/agent`. The retrieval-heavy endpoints (`/search`, `/ingest`, the evaluation routes) run in FastAPI's threadpool, which suits CPU-bound embedding work. |
| Does the Docker image work? | Yes. I cloned the repo fresh, built the image, started the container, and it reported healthy. `/health`, `/ingest`, `/search` and `/ask` all responded. Verified on Apple silicon (arm64). |
| Are there automated tests? | Yes: 32 pytest tests (text splitting, file loading, safety and groundedness checks, answer scoring, and the whole API end to end with the real embedding model and a temporary vector store). They run offline in GitHub Actions along with a Docker build. |

While writing the tests I found and fixed a real bug: a long log with no blank lines or sentence punctuation used to become a single 24,579-character chunk. It now splits into 50 chunks under 550 characters, and the sample documents chunk exactly as before.

**Findings I'm tuning next:** the groundedness check is a word-overlap heuristic, so a heavily paraphrased correct answer can score lower than it deserves; and on one test question ("what does WARN-T01 mean") the agent's search didn't surface the explaining passage, so the agent said so instead of guessing. Pointing the agent's search at the hybrid retriever is the natural fix.

## How it came together

1. **A working base.** FastAPI, ChromaDB and a React frontend, with prompt templates and experiment tracking.
2. **Azure OpenAI.** Added next to the offline fallback, so the app still works with no cloud at all.
3. **The agent and the safety layer.** A Semantic Kernel agent with real tool calls, then Content Safety and the groundedness check.
4. **Docker and deployment scripts.** The image, telemetry, and Azure Container Apps scripts.
5. **Running it for real.** I pointed everything at live Azure resources and wrote down what broke. The groundedness check was scoring correct answers too low because it compared them to a shortened excerpt, which I fixed.
6. **Making it truly async.** I converted `/ask` to async (awaited LLM and Content Safety calls), then benchmarked it. The benchmarking turned up two real bugs, both fixed: the embedding model crashed the whole process when several requests used it at once (fixed with a lock), and my first benchmark was being skewed by the free Content Safety tier's rate limit (fixed by isolating the variable). The full story is in [`bench/README.md`](bench/README.md).
7. **Checking my own claims.** I rebuilt the Docker image from a clean clone and regenerated the benchmark table from the raw JSON files.

---

## What it does

| Capability | Detail |
|---|---|
| Document ingestion | `.txt`, `.md`, `.log`, `.pdf` — chunked, embedded, stored in ChromaDB |
| Semantic + hybrid search | Cosine similarity, optionally blended with BM25 keyword matching |
| Grounded QA | `/ask` answers strictly from retrieved content, via Azure OpenAI, plain OpenAI, or a labeled retrieval-only fallback |
| Agent orchestration | `/agent` — a Semantic Kernel agent that decides whether to search documents, check equipment status, or ask a clarifying question |
| Responsible AI | Azure AI Content Safety screening (input + output) and a groundedness flag, both explicit about what's checked and what isn't |
| Prompt experimentation | Swappable system-prompt templates, side-by-side comparison, rule-based answer evaluation, experiment history |
| Source traceability | Every generated answer links back to the exact chunks, documents, and (for the agent) tool calls behind it |
| Offline-capable | The whole retrieval + evaluation pipeline works with zero cloud dependency; LLM and Content Safety are additive, not required |

---

## Architecture

```
Request
  │
  ▼
FastAPI  ─── /ingest ──────► FileLoader → TextSplitter → EmbeddingService → VectorStore (ChromaDB)
         ─── /search ──────► EmbeddingService → VectorStore.query → ChunkResults (semantic or hybrid BM25)
         ─── /ask ─────────► RetrievalService → QAService (Azure OpenAI | OpenAI | fallback)
         │                                    → SafetyService (input/output Content Safety, groundedness)
         │                                    → EvaluationService (rule-based scoring) → SQLite experiment log
         ─── /agent ────────► AgentService (Semantic Kernel) → SafetyService → AgentResponse + decision trace
         ─── /compare ──────► Same question through up to 4 prompt templates, evaluated side-by-side
         ─── /benchmark ────► 15 built-in questions run through one template, evaluated and logged
         ─── /documents ───► VectorStore.get_all_metadata → DocumentList
         ─── /health ──────► status, LLM provider, Content Safety status
```

### Agent decision flow (`POST /agent`)

This is the part that's actually agentic: the model looks at the query and decides what to do next. Nothing here is an if/else keyword router — the decision is made by the LLM via Semantic Kernel's automatic function calling, and every step it takes is logged.

```
                         ┌─────────────────────┐
                         │   User query text    │
                         └──────────┬───────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │  Content Safety: input check   │  (skipped, reported as
                    │  (Azure AI Content Safety, if   │   unchecked, if not
                    │   configured)                   │   configured)
                    └───────────────┬───────────────┘
                          flagged ──┤── clean
                            ▼        ▼
                       400 error   ┌─────────────────────────────┐
                                   │  Semantic Kernel agent        │
                                   │  (Azure OpenAI or OpenAI,     │
                                   │   whichever llm_service       │
                                   │   resolves)                   │
                                   └───────────────┬───────────────┘
                                                    │  model decides, per query:
                        ┌───────────────────────────┼───────────────────────────┐
                        ▼                            ▼                           ▼
              ┌──────────────────┐        ┌───────────────────────┐   ┌──────────────────────┐
              │ search_documents │        │ check_equipment_status │   │  Neither — the query  │
              │ (real RAG lookup, │        │ (MOCK second data      │   │  is ambiguous ("the   │
              │  same retrieval   │        │  source, canned JSON,  │   │  pump" — which one?)  │
              │  pipeline as /ask)│        │  simulates a CMMS/SCADA│   │  → ask a clarifying   │
              └─────────┬────────┘        │  status lookup)        │   │    question instead   │
                        │                  └───────────┬────────────┘   │    of guessing        │
                        │                              │                └───────────┬───────────┘
                        └──────────────┬───────────────┘                            │
                                       ▼                                            │
                         Every tool call logged: which tool,                        │
                         what arguments, what it returned                           │
                         (FUNCTION_INVOCATION filter →                              │
                         inspectable decision trace)                                │
                                       │                                            │
                                       ▼                                            ▼
                              ┌──────────────────────────────────────────────────────┐
                              │              Model composes final answer               │
                              └──────────────────────────┬─────────────────────────────┘
                                                          ▼
                                        ┌──────────────────────────────────┐
                                        │  Content Safety: output check      │
                                        │  Groundedness check (word-overlap  │
                                        │  vs. the tool results it cited)    │
                                        └──────────────────┬─────────────────┘
                                                            ▼
                                              AgentResponse: answer + full
                                              tool_calls trace + safety fields
```

### Key components

| File | Responsibility |
|---|---|
| `app/services/embedding_service.py` | Loads `all-MiniLM-L6-v2` once; generates embeddings |
| `app/services/vector_store.py` | ChromaDB wrapper — upsert, query, delete |
| `app/services/ingest_service.py` | Orchestrates load → chunk → embed → store |
| `app/services/retrieval_service.py` | Embeds query, retrieves top-k chunks (semantic or hybrid) |
| `app/services/qa_service.py` | Answer synthesis: Azure OpenAI, OpenAI, or formatted retrieval fallback |
| `app/services/llm_service.py` | Resolves which LLM backend is configured — the one place that decision is made |
| `app/services/agent_service.py` | Semantic Kernel agent: two tools, real function calling, logged decision trace |
| `app/services/safety_service.py` | Azure AI Content Safety screening + word-overlap groundedness check |
| `app/services/evaluation_service.py` | Rule-based answer scoring (groundedness, relevance, completeness, clarity, hallucination risk) |
| `app/services/experiment_service.py` | Persists every `/ask`, `/compare`, `/benchmark` run to SQLite |
| `app/services/prompt_service.py` | CRUD for swappable system-prompt templates |
| `app/utils/file_loader.py` | Extracts text from `.txt`/`.md`/`.log`/`.pdf` |
| `app/utils/text_splitter.py` | Paragraph-aware chunking with overlap |

---

## Quick Start (local, no Azure)

### Prerequisites

- Python 3.11 or higher — the pinned dependencies (`chromadb`, `sentence-transformers`) need it; a system Python 3.9 will fail to install them
- ~1 GB disk space (embedding model ~90 MB, plus `sentence-transformers`' own dependencies)

### Mac / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at **http://127.0.0.1:8000** — interactive docs at **/docs**.

With `.env` untouched (everything blank), this runs completely offline: `/ask` returns labeled retrieval excerpts, `/agent` returns a clear message that it needs an LLM backend to make tool-calling decisions, and Content Safety checks report `checked: false` instead of silently passing everything.

```bash
for f in data/sample_docs/*; do
  curl -s -X POST http://127.0.0.1:8000/ingest -F "file=@$f" > /dev/null
done
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
```

---

## Azure setup

Everything Azure-related is optional and additive — every step below can be skipped and the app still works in offline mode. This section covers what to create, why, and roughly what it costs.

### Before you start

You need an Azure subscription. Two low/no-cost ways to get one:

- **Azure for Students** (azure.microsoft.com/free/students) — $100 credit, no credit card, if you have a `.edu` email.
- **New account free credit** — $200 for 30 days on any new Azure account (requires a card on file, but nothing is charged unless you explicitly exceed the credit and choose to upgrade).

Azure OpenAI specifically also requires a one-time access request (usually fast): https://aka.ms/oai/access

### What gets created, and what it costs

| Resource | Tier used | Typical cost for this project |
|---|---|---|
| Azure OpenAI (`gpt-4.1-mini` deployment) | S0, pay-per-token | Fractions of a cent per request; a few dozen test calls is well under $1 |
| Azure AI Content Safety | F0 (free) | $0 — 5,000 text records/month included, far more than a demo needs |
| Log Analytics + Application Insights | Pay-per-GB after 5 GB free | $0 in practice for occasional demo traffic |
| Azure Container Apps | Consumption plan | $0 in practice — 180,000 vCPU-seconds/month free, and `--min-replicas 0` scales to zero when idle |

Deliberately **not** using Azure Container Registry (Basic tier is ~$5/month, continuously) — the deployment script pushes to a free registry (GitHub Container Registry or Docker Hub) instead. See `deploy/azure_setup.sh`.

### Provisioning

```bash
az login
bash deploy/azure_setup.sh
```

The script pauses before every billable step, prints the estimated cost, and waits for you to press Enter. It follows the Azure CLI's documented syntax, so run it in Cloud Shell (or any shell with `az`) and check each command's output as you go. `deploy/azure_teardown.sh <resource-group>` deletes everything again when you're done demoing.

Once you have real values, fill them into `.env` (copy from `.env.example`):

```bash
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=gpt-41-mini
AZURE_OPENAI_API_VERSION=2024-10-21

AZURE_CONTENT_SAFETY_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_CONTENT_SAFETY_KEY=<key>

APPLICATIONINSIGHTS_CONNECTION_STRING=<connection string>
```

Restart the server; `GET /health` will now report `llm_provider: "azure_openai"` and `content_safety_enabled: true`.

---

## API Reference

### `GET /health`

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "indexed_documents": 4,
  "total_chunks": 65,
  "llm_available": false,
  "llm_provider": "none",
  "content_safety_enabled": false
}
```
This is real output from a local run with no keys configured — `llm_provider` and `content_safety_enabled` tell you exactly what's active without having to inspect `.env` yourself.

### `POST /ingest`, `GET /documents`, `POST /search`, `DELETE /documents/{doc_id}`

Unchanged from the base project — see inline `/docs` for full request/response shapes. `/search` accepts `use_hybrid: true` to blend BM25 keyword matching with semantic similarity (`hybrid_alpha` controls the blend, default 0.7 = mostly semantic).

### `POST /ask`

Grounded QA. Adds three fields on top of the original response: `llm_provider` (which backend actually answered), `input_safety` / `output_safety` (Content Safety results), and `groundedness_flag` (the word-overlap check, separate from the existing continuous `evaluation.groundedness_score`).

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What should I check if the hydraulic pump overheats?", "top_k": 3}'
```

Real response, fallback mode (no LLM configured):
```json
{
  "question": "What should I check if the hydraulic pump overheats?",
  "answer": "⚠️  LLM synthesis is not enabled...",
  "llm_used": false,
  "llm_provider": "none",
  "retrieval_count": 3,
  "sources": [ ... ],
  "input_safety": {"checked": false, "flagged": false, "categories": {}, "note": "Content Safety not configured..."},
  "output_safety": {"checked": false, "flagged": false, "categories": {}, "note": "Content Safety not configured..."},
  "groundedness_flag": {"grounded": true, "overlap_ratio": 0.6512, "method": "word_overlap"}
}
```

### `POST /agent`  — new in this edition

```bash
curl -X POST http://127.0.0.1:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Is HX-9000 currently showing any faults?"}'
```

With no LLM configured, real response:
```json
{
  "query": "Is HX-9000 currently showing any faults?",
  "answer": "Agent orchestration needs a configured LLM backend (Azure OpenAI or OpenAI) to decide which tool to call — there is no model available right now to make that decision, and this project does not fake agentic behavior without one. Configure AZURE_OPENAI_* or OPENAI_API_KEY in .env, or use POST /ask for retrieval-only mode.",
  "llm_used": false,
  "llm_provider": "none",
  "tool_calls": []
}
```

With a real LLM configured, the response has this shape (live runs are summarized in "What's verified live" below):
```json
{
  "query": "Is HX-9000 currently showing any faults?",
  "answer": "HX-9000 is currently operational with no active fault codes...",
  "llm_used": true,
  "llm_provider": "azure_openai",
  "tool_calls": [
    {
      "tool": "equipment.check_equipment_status",
      "arguments": {"equipment_id": "HX-9000"},
      "result_excerpt": "{\"equipment_id\": \"HX-9000\", \"status\": \"operational\", ...}"
    }
  ],
  "input_safety": {"checked": true, "flagged": false, "categories": {"Hate": 0, "SelfHarm": 0, "Sexual": 0, "Violence": 0}},
  "output_safety": {"checked": true, "flagged": false, "categories": {"Hate": 0, "SelfHarm": 0, "Sexual": 0, "Violence": 0}},
  "groundedness": {"grounded": true, "overlap_ratio": 0.55, "method": "word_overlap"}
}
```

### `POST /prompts`, `POST /compare`, `POST /evaluate`, `GET /experiments*`, `GET/POST /benchmark/*`

Unchanged v2 features (prompt template CRUD, side-by-side comparison, rule-based evaluation, experiment history, built-in 15-question benchmark). See `/docs` for full schemas. Content Safety screening is deliberately **not** applied to `/compare` or `/benchmark` — both can fan out to many LLM calls per request (up to 4 templates, or 15 benchmark questions), and adding a Content Safety call per generated answer there would multiply API usage for what's fundamentally an internal evaluation tool, not a user-facing answer path. `/ask` and `/agent` are the two endpoints that actually return answers to an end user, so that's where the safeguards are applied.

---

## Agent orchestration — design notes

The point of Phase 2 wasn't "call an LLM and have it use a tool" — a single hardcoded tool call isn't a decision. The agent has **two** genuinely different tools (`search_documents`, wrapping the real retrieval pipeline; `check_equipment_status`, a mock second data source with canned JSON), and the system prompt gives the model room to pick neither and ask a clarifying question instead. Which of those three outcomes happens is decided by the model reading the actual query text, via Semantic Kernel's `FunctionChoiceBehavior.Auto()` — not a keyword match on "pump" or "equipment ID" in application code.

`check_equipment_status` is explicitly mock data — a small hand-written dictionary (`HX-9000`, `SCU-400`, `PUMP-01`, matching equipment names that already appear in the sample documents), not a live system. It exists to prove the agent can choose between two real tools, not to simulate a real CMMS. This is stated in the code and here, not hidden.

Every tool invocation is captured by a Semantic Kernel `FUNCTION_INVOCATION` filter and returned in the API response as `tool_calls`: which tool, what arguments, what it returned (truncated to 300 characters). That's the actual deliverable of this phase — an agent whose reasoning can be inspected and audited after the fact, not a black box you have to trust.

### What's verified live

Verified live on 2026-09-21 against a real Azure OpenAI deployment (`gpt-4.1-mini`, GlobalStandard, North Central US, an Azure for Students subscription) and a real Azure AI Content Safety resource (F0 tier):

- **Real function calling, with different decisions per query.** Four agent queries, four different behaviours: a how-to question called only `documents.search_documents`; a status question called only `equipment.check_equipment_status`; a vague question ("It keeps failing, what do I do?") called **no tool** and asked a clarifying question; a compound question called **both**, in sequence. Each tool call, its arguments and its result were captured in the `tool_calls` trace. These are four hand-picked queries that show the decision-making; a scored tool-selection evaluation is the natural next step.
- **`/ask` through Azure OpenAI** returned a synthesised, cited answer (`llm_provider: azure_openai`).
- **Content Safety is a real call.** A violent input was rejected with HTTP 400 by the live service; a benign query and its answer returned severity 0 in all four categories.
- The offline fallback, provider resolution, graceful failure on a bad key, Azure Monitor wiring and every v2 feature were also verified earlier (see above).

Findings from that live run, and what was done:

- The groundedness check first compared answers to the 300-character *display* excerpt of each tool result, so correct answers scored 0.10-0.14 overlap and were flagged. Fixed to compare against the full tool output (correct answers then scored 0.50 and 0.77).
- **Tuning opportunity:** a short, correct paraphrase of a JSON tool result (the equipment-status answer) scores 0.20 and is flagged `grounded: false`. That is how a word-overlap heuristic behaves; I kept it as measured, and a semantic entailment check is the upgrade path.
- **Retrieval note:** asked "what does WARN-T01 mean", the agent's search query didn't surface the passage explaining the code even though the sample documents mention it, and the agent said so instead of inventing an answer. Code-like tokens are where keyword search shines, so pointing the agent's search tool at the hybrid retriever (`use_hybrid`, already implemented) is the next improvement.

**Deployment:** the Azure OpenAI and Content Safety resources used here were created by hand in Cloud Shell, and `deploy/azure_setup.sh` plus the Container Apps rollout are ready to run end to end as the next step.

---

## Responsible AI safeguards

### Content Safety

`POST /ask` and `POST /agent` screen both the input query and the generated output through Azure AI Content Safety, when `AZURE_CONTENT_SAFETY_ENDPOINT` and `AZURE_CONTENT_SAFETY_KEY` are set. A flagged **input** returns an HTTP 400 before any retrieval or generation happens. A flagged **output** is reported in the response (`output_safety.flagged: true`) rather than silently swapped for something else — for an engineering-documentation assistant, an answer quoting a hazard warning verbatim from a manual could plausibly trip a safety category without actually being unsafe in context, and quietly rewriting it would hide useful information. Flag it, show it, let a human decide.

**When it isn't configured:** requests run unscreened and the response says `checked: false`, so "checked and clean" is never confused with "not checked". When it runs, it is a real Azure API call against Azure's moderation categories (hate, self-harm, sexual, violence), not a hand-rolled keyword blocklist.

### Groundedness

Every `/ask` and `/agent` response includes a `grounded: true/false` flag, in addition to `/ask`'s existing continuous `evaluation.groundedness_score`. It's a word-overlap check: what fraction of the answer's "meaningful" words (5+ characters) also appear in the source text it was supposedly grounded in — retrieved chunks for `/ask`, tool-call result excerpts for `/agent`. Below a 30% overlap, it's flagged.

**How to read it:** it's a word-overlap check, so a heavily paraphrased answer can score lower than its accuracy deserves, and an unsupported claim that reuses the source's words can score higher. The 30% threshold is a documented starting point; with real usage data, watch the false-positive and false-negative rate and adjust `_GROUNDEDNESS_THRESHOLD` in `app/services/safety_service.py`.

---

## Deployment

### Docker

```bash
docker build -t rag-assistant .
docker run -p 8000:8000 --env-file .env rag-assistant
```

The embedding model is baked into the image at build time, so a fresh container is ready to serve immediately without needing to reach Hugging Face at runtime — only whichever LLM/Content Safety endpoints are configured, if any.

**Verified**: built from a clean clone and run (Apple silicon, Docker 29.8.0); `/health`, `/ingest`, `/search` and `/ask` (offline mode) all worked. **Not verified**: amd64 builds, and running the container against live Azure endpoints.

### Azure Container Apps

```bash
docker build -t rag-assistant .
docker tag rag-assistant ghcr.io/YOUR_GITHUB_USERNAME/rag-assistant:latest
docker push ghcr.io/YOUR_GITHUB_USERNAME/rag-assistant:latest
# then edit IMAGE in deploy/azure_setup.sh to match, and run it
bash deploy/azure_setup.sh
```

**Storage note:** ChromaDB and the SQLite experiments database live inside the container filesystem, so by default they reset on a restart or new revision. That suits a demo where you re-ingest documents each time, and it keeps the default deployment simple and cheap, which is why `deploy/azure_setup.sh` doesn't set up a volume. If you want documents to survive restarts, add an Azure Files share and mount it at `/app/data` in the container app; that's a genuinely separate piece of work from what's here.

### Telemetry — Azure Monitor / Application Insights

Set `APPLICATIONINSIGHTS_CONNECTION_STRING` and restart. This does two things automatically, with zero changes to any individual `logger.info()`/`logger.warning()` call in the codebase:
- Every existing log line starts shipping to Application Insights as a trace entry
- FastAPI request/response tracing (latency, status codes, exceptions) is added automatically via `FastAPIInstrumentor`

With it unset, telemetry stays exactly what it always was: local stdout logging. Nothing about local behavior changes either way.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model name |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` | Chunking parameters |
| `DEFAULT_TOP_K` | `5` | Default retrieved-chunk count |
| `HYBRID_ALPHA` | `0.7` | Semantic vs. BM25 blend weight for hybrid search |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | _(empty)_ / `gpt-3.5-turbo` / OpenAI's API | Plain OpenAI, used if Azure OpenAI isn't fully configured |
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` / `_API_VERSION` | _(empty)_ | Azure OpenAI — all three of endpoint/key/deployment must be set to activate; tried before plain OpenAI |
| `AZURE_CONTENT_SAFETY_ENDPOINT` / `_KEY` | _(empty)_ | Both must be set to enable safety screening |
| `CONTENT_SAFETY_SEVERITY_THRESHOLD` | `4` | Azure's severity scale is 0/2/4/6; flag at or above this |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | _(empty)_ | Enables Azure Monitor telemetry when set |
| `CHROMA_DB_PATH` / `EXPERIMENTS_DB_PATH` | `data/chroma_db` / `data/experiments.db` | Local persistence paths |

---

## What I ran into building this

The base project's own README documented v1, but the shipped code was already v2 — prompt templates, comparison, evaluation, experiment tracking, none of it mentioned in the docs. Worth reading the actual source before trusting a project's README, including this one; I read every service file before writing a line of new code, and it changed the scope of Phase 3 significantly (a groundedness scorer already existed — the work was extending it into an explicit flag/decision and wiring in Content Safety alongside it, not building groundedness checking from scratch).

Getting the base project running on current dependencies took one fix. `pip install -r requirements.txt` pulled FastAPI 0.141 and Starlette 1.6 (the requirements file pins only a floor, `fastapi>=0.104.0`), and a startup log line, `[r.path for r in app.routes]`, assumed every registered route has a `.path` attribute. In current Starlette, included sub-routers are a different internal type without one. The one-line fix is `if hasattr(r, "path")`, in the second commit.

The Dockerfile is new in this edition: I wrote it from scratch and verified it by building from a clean clone.

The most interesting design question was how to prove the Azure pieces really work. The answer was a set of deliberate checks: a syntactically valid but fake OpenAI key, to confirm requests reach the provider and failures degrade gracefully, and then live runs against real Azure resources (see "What's verified live").

Scoping Content Safety to `/ask` and `/agent` but not `/compare` or `/benchmark` was a deliberate cost/rate-limit tradeoff, not an oversight — `/benchmark` alone fans out to 15 LLM calls per run, and adding a Content Safety call per generated answer on top of that changes the cost profile of what's meant to be an internal evaluation tool. Worth knowing if you extend this and want safety screening everywhere.

---

## Scope and roadmap

**What this is:** a working, source-attributed RAG pipeline with an agentic layer on top, built on real Azure services and not mocks, with each piece exercised and the results recorded in `docs/VERIFICATION.md`.

**Where I'd take it next:**
- **Persistence:** mount an Azure Files share for ChromaDB and the experiments database in Container Apps.
- **Auth and rate limiting:** add an API key or user layer. Today the app is designed to sit behind a firewall, because some endpoints spend Azure OpenAI budget.
- **Semantic groundedness:** replace word overlap with an entailment check.
- **A real equipment data source:** the equipment-status tool uses three hand-written records to demonstrate real tool selection; a CMMS or SCADA integration would be the production version.
- **A tool-call policy layer:** approve or reject an agent's tool call before it runs. Today the decision trace is logged and can be inspected afterwards.
- **Broader load testing** beyond the benchmark in `bench/`.

---

## Project structure

```
RAG_document_log_assistant/
├── app/
│   ├── main.py                       # FastAPI app, lifespan, Azure Monitor wiring
│   ├── api/
│   │   ├── routes.py                 # v1: ingest, search, ask, documents, health
│   │   ├── eval_routes.py            # v2: prompts, compare, evaluate, experiments, benchmark
│   │   └── agent_routes.py           # v3: agent
│   ├── core/
│   │   ├── config.py                 # Settings (pydantic-settings) — all env vars
│   │   └── logging_config.py
│   ├── models/schemas.py             # All request/response Pydantic models
│   ├── services/
│   │   ├── embedding_service.py
│   │   ├── vector_store.py
│   │   ├── ingest_service.py
│   │   ├── retrieval_service.py      # semantic + hybrid BM25
│   │   ├── llm_service.py            # v3: Azure OpenAI / OpenAI / none resolution
│   │   ├── qa_service.py
│   │   ├── agent_service.py          # v3: Semantic Kernel agent + tools
│   │   ├── safety_service.py         # v3: Content Safety + groundedness
│   │   ├── evaluation_service.py
│   │   ├── experiment_service.py
│   │   └── prompt_service.py
│   ├── db/                           # SQLite: prompt templates, experiment runs, evaluations
│   └── utils/
│       ├── file_loader.py
│       └── text_splitter.py
├── deploy/
│   ├── azure_setup.sh                # Provisions Azure OpenAI, Content Safety, Container Apps, etc.
│   └── azure_teardown.sh
├── frontend/                          # React/TypeScript UI (ask, search, upload, compare, evaluate, dashboard)
├── data/sample_docs/                  # Ready-to-ingest engineering documents
├── tests/benchmark_questions.json     # 15 built-in benchmark questions
├── Dockerfile
├── .dockerignore
├── .env.example
├── requirements.txt
└── README.md
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi`, `uvicorn` | Web framework, ASGI server |
| `chromadb` | Local persistent vector database |
| `sentence-transformers` | Local embedding model |
| `rank-bm25` | Hybrid keyword search |
| `pypdf` | PDF text extraction |
| `openai` | Both plain OpenAI and Azure OpenAI (via `AzureOpenAI` client) |
| `semantic-kernel` | Agent orchestration, function calling |
| `azure-ai-contentsafety` | Content Safety screening |
| `azure-monitor-opentelemetry` | Application Insights telemetry |
| `pydantic-settings` | Typed configuration from `.env` |

---

## License

MIT — free to use, modify, and include in your portfolio.
