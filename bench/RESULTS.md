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

## Reading these honestly
- **Each saved run is a single wave of N requests at concurrency N** (total_requests = concurrency). With so few requests, p95 is effectively the max and single runs are noisy; the earlier 4-repeat table in `README.md` (sync 27-66 vs async 92-101 req/s at c=20) is the better evidence for the offline result, but only the one run per cell is preserved as raw JSON here.
- **Offline mode:** async is faster at c=20 in the saved run and in the README's repeats. At c=80 the saved runs show sync ahead (see table). Do not generalize beyond ~20 concurrent.
- **Live Azure mode:** no consistent difference between sync and async; Azure's per-deployment throttling was the bottleneck. Not claimed as an improvement.
- The `~38 req/s` figure appears in no measurement. It must not be used.
