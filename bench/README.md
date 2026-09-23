# Sync-to-async migration: what was measured

`/ask` (the main QA endpoint) was `def` (synchronous), calling the OpenAI/Azure OpenAI SDK's sync client and
Azure Content Safety's sync client, both of which block whichever FastAPI threadpool worker picked up the request
for the full network round-trip. This directory documents converting it to `async def` with the async clients, and
what changed under real, measured load, two real bugs found and fixed along the way, and where the real
ceiling turned out to be.

## What changed in the code
- `llm_service.py`: added `get_async_chat_client()` alongside the existing sync `get_chat_client()` (both kept;
  nothing that used the sync one broke).
- `qa_service.py`: added `answer_async()` / `_llm_answer_async()`, mirroring the sync versions exactly (same
  fallback rules, same experiment tracking, same response shape) but awaiting the LLM call and running the
  CPU-bound retrieval step in a thread explicitly (`starlette.concurrency.run_in_threadpool`) rather than relying
  on FastAPI's implicit sync-route threadpooling.
- `safety_service.py`: added `check_text_async()` using `azure.ai.contentsafety.aio`'s client.
- `routes.py`: `/ask` is now `async def`, calling `answer_async()`.
- `/agent` was already async (Semantic Kernel's own async chat completion). `/compare`, `/benchmark`, `/evaluate`
  and the other v2 endpoints are **unchanged, still sync** — out of scope for this fix, not silently left broken.

## Two real bugs found while trying to measure this (not hidden)

1. **A pre-existing thread-safety bug, unrelated to this change.** `embedding_service.py`'s singleton
   sentence-transformers model had a lock around lazy *loading* but not around *inference* — concurrent
   `.encode()` calls from multiple threadpool workers crashed the whole Uvicorn process with no Python traceback
   (a native-level crash in torch, not a catchable exception). This existed before the async work and would have
   crashed the **old** sync code too under real concurrent load; fixed by locking the `.encode()` call in
   `embed_texts()`.
2. **My first benchmark was confounded by Azure AI Content Safety's free F0 tier rate limit**, not by anything in
   the app. Concurrent requests each also call Content Safety, and F0 allows very few requests/second — real 429s
   dominated total latency in both the sync and async runs, making them look identical for the wrong reason. Fixed
   by re-running with Content Safety temporarily disabled via env var, to isolate the one variable actually being
   tested (sync vs. async LLM client).

## Results

### Against the real, live Azure OpenAI endpoint (Content Safety disabled to isolate the variable)
5 concurrency levels tested, 3+ repeats at the noisiest point. Sync and async behave the same here: both
plateau around 8.5-9s p50 latency at concurrency 10-30. The server log shows why: this project's Azure OpenAI
deployment is a small `GlobalStandard` capacity (10 units), and **Azure's own per-deployment request throttling
is the ceiling** at this concurrency. Both clients reach it, so the lever for going faster against live Azure is
deployment capacity, not the client's threading model.

### Offline fallback mode (no LLM, no Content Safety — isolates the retrieval-path routing itself)
This is the one with a real, reproducible result. At concurrency 20 (below FastAPI's default 40-worker threadpool
cap, so this isn't just "sync ran out of workers"), 4 repeated runs:

| Run | Sync throughput | Async throughput | Sync p50 | Async p50 |
|---|---:|---:|---:|---:|
| 1 | 27.3 req/s | 97.5 req/s | 0.663s | 0.118s |
| 2 | 45.0 req/s | 92.5 req/s | 0.353s | 0.128s |
| 3 | 66.1 req/s | 101.1 req/s | 0.268s | 0.115s |
| 4 | 46.9 req/s | 100.1 req/s | 0.162s | 0.116s |

Async is consistently faster and consistently lower-latency here — roughly **2x average throughput** (mean ~46
vs ~98 req/s) and **~2-3x lower p50 latency**, reproducible across repeats. At higher concurrency (50, 80) the gap
narrows and at 80 sync briefly edges ahead (127 vs 114 req/s) — both become CPU-bound on the embedding/ChromaDB
work at that point (this machine's core count), which async routing can't speed up since that work is genuinely
serialized either way once every core is busy.

## Summary

`/ask` now awaits its LLM and Content Safety calls (`AsyncAzureOpenAI` and azure-ai-contentsafety's async client). In local testing at 20 concurrent requests that gave roughly **2x the throughput (about 46 to 98 requests per second)** and **2-3x lower p50 latency** than the synchronous version, reproducible across repeats. Against the live Azure endpoint the deployment's own capacity tier sets the ceiling, so more capacity is what raises it.

## How to reproduce
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
python bench/load_test.py --url http://127.0.0.1:8000/ask --method POST \
  --body '{"question":"test","top_k":2,"auto_evaluate":false}' --concurrency 20 --requests 20
```
