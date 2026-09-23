# What I actually ran, and what came out

Dated notes so anyone (including me, later) can see what has been checked and what hasn't.
Machine: Apple M4, 10 cores, 16 GB RAM, macOS 26.5.1, Docker Desktop 29.8.0 (arm64).

## Docker build and run from a clean clone (2026-09-23)

Cloned the repo into a temporary folder (files identical to commit `b3dbec7`, the async change), then:

```
docker build -t rag-assistant-verify .        # exit code 0
docker run -d -p 18000:8000 rag-assistant-verify
```

`GET /health` returned:

```json
{"status":"healthy","version":"2.0.0","indexed_documents":0,"total_chunks":0,
 "llm_available":false,"llm_provider":"none","content_safety_enabled":false}
```

The container's own health check reported `healthy` after about 50 seconds. Then, with no Azure keys configured:

- `POST /ingest` with `data/sample_docs/manual.txt` created 17 chunks
- `POST /search` returned ranked passages
- `POST /ask` returned the offline fallback answer with its source passages
- The container logs contained no tracebacks or errors

Not tried: an amd64 build, running the container against live Azure endpoints, deploying to Azure Container Apps (the scripts in `deploy/` have never been run end to end, because my university tenant blocks the Azure CLI from this machine).

## Live Azure checks (2026-09-21)

Against a real Azure OpenAI deployment (`gpt-4.1-mini`, GlobalStandard, North Central US) and a real Azure AI Content Safety resource (F0 tier): four agent queries produced four different tool decisions, `/ask` returned a cited synthesized answer, and a violent input was rejected with HTTP 400 by Content Safety. Details and the defects found are in the main README.

## Async benchmark

See [`../bench/RESULTS.md`](../bench/RESULTS.md) (table generated from the raw JSON files) and [`../bench/README.md`](../bench/README.md) (the story, including the two bugs found along the way). One thing to keep in mind when reading the table: each saved run is a single burst of N requests at concurrency N, so a single run is noisy. The four repeated offline runs at concurrency 20 are described in `bench/README.md`, but only the first run's raw JSON was kept.

## Secrets check (2026-09-23)

I compared the four real values in my local `.env` (Azure OpenAI endpoint and key, Content Safety endpoint and key) against every commit in the repository history. None of them appear anywhere. `.env` is git-ignored and only `.env.example` files with empty placeholders are tracked.

## Automated tests (2026-09-23)

`python -m pytest tests -q`: 32 passed (offline, temporary vector store, no cloud services). Writing them exposed a chunking bug: a 400-line log with no blank lines or sentence punctuation became one 24,579-character chunk. After the fix it splits into 50 chunks (max 546 characters) and the four sample documents chunk exactly as before (17, 15, 10 and 23 chunks). Regression tests cover it.

## Not done yet

- No amd64 image test
- No Container Apps deployment
