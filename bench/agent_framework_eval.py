"""Compare the Semantic Kernel and LangChain versions of the same agent.

Both agents share the system prompt, the two tools, the JSON response format
and the validate-and-retry loop; only the framework differs. Each runs the 21
labeled questions in bench/agent_tool_questions.json against the LLM backend
configured in .env, for --runs passes, alternating framework order per
question so neither always goes first.

Scored per turn:
  tool choice correct  the set of tools called equals expected_tools
                       (an empty set for a clarifying question)
  validated            the JSON answer passed the schema check (first try or retry)
  seconds              wall time for the whole turn (each turn times out at 120 s)

Run:  python bench/agent_framework_eval.py --runs 2
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp(prefix="rag_framework_eval_")
os.environ["CHROMA_DB_PATH"] = os.path.join(tmp, "chroma")
os.environ["EXPERIMENTS_DB_PATH"] = os.path.join(tmp, "experiments.db")
sys.path.insert(0, str(ROOT))

from app.services import agent_langchain, agent_service, ingest_service, llm_service  # noqa: E402

TURN_TIMEOUT = 120

FRAMEWORKS = {
    "semantic_kernel": agent_service.run_agent,
    "langchain": agent_langchain.run_agent,
}


def short_name(tool: str) -> str:
    return tool.split(".")[-1]


async def run_one(framework: str, q: dict) -> dict:
    start = time.perf_counter()
    try:
        res = await asyncio.wait_for(FRAMEWORKS[framework](q["question"]), TURN_TIMEOUT)
    except asyncio.TimeoutError:
        return {"framework": framework, "id": q["id"], "category": q["category"],
                "expected": sorted(q["expected_tools"]), "called": [], "tool_choice_correct": False,
                "n_tool_calls": 0, "llm_ok": False, "validated": False, "attempts": None,
                "seconds": TURN_TIMEOUT, "answer": "TIMEOUT"}
    seconds = time.perf_counter() - start
    called = sorted({short_name(tc.tool) for tc in res.tool_calls})
    meta = res.structured_meta
    return {
        "framework": framework,
        "id": q["id"],
        "category": q["category"],
        "expected": sorted(q["expected_tools"]),
        "called": called,
        "tool_choice_correct": called == sorted(q["expected_tools"]),
        "n_tool_calls": len(res.tool_calls),
        "llm_ok": res.llm_used,
        "validated": bool(meta and meta.validated),
        "attempts": meta.attempts if meta else None,
        "seconds": round(seconds, 2),
        "answer": res.answer[:200],
    }


def summarise(rows: list[dict]) -> dict:
    by_cat = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["category"]][0] += r["tool_choice_correct"]
        by_cat[r["category"]][1] += 1
    return {
        "turns": len(rows),
        "tool_choice_correct": sum(r["tool_choice_correct"] for r in rows),
        "by_category": {c: f"{ok}/{n}" for c, (ok, n) in sorted(by_cat.items())},
        "validated": sum(r["validated"] for r in rows),
        "needed_retry": sum(r["validated"] and (r["attempts"] or 0) > 1 for r in rows),
        "llm_failures": sum(not r["llm_ok"] for r in rows),
        "median_seconds": statistics.median(r["seconds"] for r in rows),
        "mean_tool_calls": round(statistics.mean(r["n_tool_calls"] for r in rows), 2),
    }


async def main(runs: int, out: Path) -> None:
    resolved = llm_service.resolve()
    if resolved.provider == "none":
        sys.exit("No LLM backend configured in .env; nothing to measure.")
    for doc in sorted((ROOT / "data" / "sample_docs").iterdir()):
        ingest_service.ingest_file(str(doc), original_filename=doc.name)
    questions = json.loads((ROOT / "bench" / "agent_tool_questions.json").read_text())["questions"]

    rows = []
    for run in range(1, runs + 1):
        for i, q in enumerate(questions):
            order = list(FRAMEWORKS) if (i + run) % 2 else list(reversed(FRAMEWORKS))
            for fw in order:
                r = await run_one(fw, q)
                r["run"] = run
                rows.append(r)
                print(f"run {run} {fw:15s} {q['id']} expected={r['expected']} called={r['called']} "
                      f"ok={r['tool_choice_correct']} valid={r['validated']} {r['seconds']}s", flush=True)

    result = {
        "provider": resolved.provider,
        "model": resolved.model,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runs": runs,
        "questions": len(questions),
        "summary": {fw: summarise([r for r in rows if r["framework"] == fw]) for fw in FRAMEWORKS},
        "rows": rows,
    }
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--out", default="bench/agent_framework_results.json")
    args = parser.parse_args()
    asyncio.run(main(args.runs, ROOT / args.out))
