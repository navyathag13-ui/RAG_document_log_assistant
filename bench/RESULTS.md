# Benchmark results (generated from raw JSON in this directory)

Machine: Apple M4, 10 cores, 16 GB RAM, macOS 26.5.1. Tool: `load_test.py` (asyncio client). Endpoint: `POST /ask`.
`sync` = the pre-async `/ask` path (commit before 7078e4e); `async` = commit 7078e4e.

Modes: `clean` = live Azure OpenAI (gpt-4.1-mini, 10-unit GlobalStandard deployment), Content Safety disabled to isolate the variable;
`fallback` = offline, no LLM, no Content Safety (retrieval-only).

| Mode | Concurrency | Variant | Requests | Errors (non-200+exc) | Req/s | p50 (s) | p95 (s) | File date |
|---|---|---|---|---|---|---|---|---|
| clean | 5 | async | 5 | 0 | 0.41 | 1.1323 | 12.2397 | 2026-09-22 |
| clean | 5 | sync | 5 | 0 | 2.5 | 1.3475 | 1.9751 | 2026-09-22 |
| clean | 10 | async | 10 | 0 | 1.05 | 8.8586 | 9.5274 | 2026-09-22 |
| clean | 10 | sync | 10 | 0 | 1.04 | 8.8415 | 9.6173 | 2026-09-22 |
| clean | 15 | async | 15 | 0 | 1.6 | 8.5078 | 9.3526 | 2026-09-22 |
| clean | 15 | sync | 15 | 0 | 1.47 | 9.0133 | 10.2034 | 2026-09-22 |
| clean | 20 | async | 20 | 0 | 2.0 | 8.975 | 9.997 | 2026-09-22 |
| clean | 20 | sync | 20 | 0 | 2.08 | 8.8955 | 9.5757 | 2026-09-22 |
| clean | 30 | async | 30 | 0 | 2.96 | 8.5759 | 9.9585 | 2026-09-22 |
| clean | 30 | sync | 30 | 0 | 3.08 | 8.6037 | 9.0479 | 2026-09-22 |
| fallback | 20 | async | 20 | 0 | 97.51 | 0.1176 | 0.1918 | 2026-09-22 |
| fallback | 20 | sync | 20 | 0 | 27.3 | 0.663 | 0.7116 | 2026-09-22 |
| fallback | 50 | async | 50 | 0 | 107.33 | 0.243 | 0.4338 | 2026-09-22 |
| fallback | 50 | sync | 50 | 0 | 97.06 | 0.2914 | 0.4811 | 2026-09-22 |
| fallback | 80 | async | 80 | 0 | 114.31 | 0.5529 | 0.6579 | 2026-09-22 |
| fallback | 80 | sync | 80 | 0 | 126.85 | 0.329 | 0.5908 | 2026-09-22 |

## Reading the results
- **Each saved run is a single wave of N requests at concurrency N.** p95 is effectively the max at that size. The earlier 4-repeat table in `README.md` (sync 27-66 vs async 92-101 req/s at c=20) is the stronger evidence for the offline result; one raw run per cell is preserved here.
- **Offline mode:** async is faster at c=20, both in the saved run and in the README's repeats. By c=80 both versions are limited by CPU, where the saved runs show sync slightly ahead (see table). The clearest win is around 20 concurrent requests.
- **Live Azure mode:** sync and async match, because Azure's per-deployment throttling is the ceiling. More capacity is how to go faster there.
- Every number in this file comes from the raw JSON in this directory.

## Retrieval quality (2026-09-23)

`python bench/retrieval_eval.py` ingests the four sample documents into a temporary store and scores the 15 built-in benchmark questions (`tests/benchmark_questions.json`). Each question names the document that should answer it and keywords a good passage should contain.

| Mode | Correct document at rank 1 | in top 3 | in top 5 | Expected keywords found in top-3 text |
|---|---|---|---|---|
| Semantic only | 86.7% (13/15) | 100% | 100% | 71.3% |
| Hybrid, alpha 0.7 (the app's default) | 93.3% (14/15) | 100% | 100% | 78.9% |
| Hybrid, alpha 0.5 | 93.3% (14/15) | 100% | 100% | 76.4% |
| Keyword-heavy, alpha 0.2 | 73.3% (11/15) | 100% | 100% | 79.1% |

Context: 15 questions over four documents (about 65 chunks), so one question moves a number by 6.7 points. The four modes were fixed before running and 0.7 was already the default, so nothing was tuned on this set. It shows blending keyword search into semantic search helps at rank 1 here; a larger corpus is the next test. Raw output: `retrieval_eval_results.json`.
