"""Concurrent load test: fires N concurrent requests at a running server and reports real throughput.

Usage: python bench/load_test.py --url http://127.0.0.1:8000/ask --concurrency 50 --requests 300 --method POST --body '{"question":"What temperature triggers FAULT-T02?","top_k":3}'
Real numbers only: measures actual wall-clock time for the batch, reports req/s, p50/p95/p99 latency from the
actual responses received. No requests are simulated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

import httpx


async def one_request(client: httpx.AsyncClient, url: str, method: str, body: dict | None) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = await (client.post(url, json=body) if method == "POST" else client.get(url))
    dt = time.perf_counter() - t0
    return dt, r.status_code


async def run(url: str, concurrency: int, total: int, method: str, body: dict | None) -> dict:
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=60.0, limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)

        async def bound():
            async with sem:
                return await one_request(client, url, method, body)

        t0 = time.perf_counter()
        results = await asyncio.gather(*[bound() for _ in range(total)], return_exceptions=True)
        wall = time.perf_counter() - t0

    latencies = [r[0] for r in results if isinstance(r, tuple)]
    statuses = [r[1] for r in results if isinstance(r, tuple)]
    errors = [r for r in results if not isinstance(r, tuple)]
    latencies.sort()
    def pct(p):
        return round(latencies[min(len(latencies) - 1, int(len(latencies) * p))], 4) if latencies else None
    return {
        "total_requests": total, "concurrency": concurrency, "wall_seconds": round(wall, 3),
        "throughput_req_s": round(total / wall, 2), "ok_200": statuses.count(200), "non_200": len([s for s in statuses if s != 200]),
        "exceptions": len(errors), "latency_p50_s": pct(0.50), "latency_p95_s": pct(0.95), "latency_p99_s": pct(0.99),
        "latency_min_s": round(min(latencies), 4) if latencies else None, "latency_max_s": round(max(latencies), 4) if latencies else None,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--body", default=None)
    a = ap.parse_args()
    body = json.loads(a.body) if a.body else None
    out = asyncio.run(run(a.url, a.concurrency, a.requests, a.method, body))
    print(json.dumps(out, indent=2))
