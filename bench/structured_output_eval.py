"""Measure how often the live model's structured output validates.

Runs the 15 benchmark questions through both the /ask path
(qa_service.answer_with_template) and the /agent path (agent_service.run_agent)
against the LLM backend configured in .env, with the four sample documents
ingested into a temporary vector store. For each answer it records whether the
JSON validated on the first try, needed the retry, or fell back.

Needs a configured LLM backend (Azure OpenAI or OpenAI); refuses to run without one.

Run:  python bench/structured_output_eval.py
"""
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp(prefix="rag_structured_eval_")
os.environ["CHROMA_DB_PATH"] = os.path.join(tmp, "chroma")
os.environ["EXPERIMENTS_DB_PATH"] = os.path.join(tmp, "experiments.db")
sys.path.insert(0, str(ROOT))

from app.services import agent_service, ingest_service, llm_service, qa_service  # noqa: E402

resolved = llm_service.resolve()
if resolved.provider == "none":
    sys.exit("No LLM backend configured in .env; nothing to measure.")

for doc in sorted((ROOT / "data" / "sample_docs").iterdir()):
    ingest_service.ingest_file(str(doc), original_filename=doc.name)

questions = json.loads((ROOT / "tests" / "benchmark_questions.json").read_text())["questions"]


def row(qid, meta, ans, seconds, sources=None):
    return {
        "id": qid,
        "validated": meta.validated,
        "attempts": meta.attempts,
        "fallback_used": meta.fallback_used,
        "last_error": meta.last_error,
        "n_cited": len(ans.cited_chunk_ids) if ans else 0,
        "cited_primary_doc": None if sources is None else any(s.startswith(sources) for s in ans.cited_chunk_ids),
        "confidence": ans.confidence if ans else None,
        "needs_human_review": ans.needs_human_review if ans else None,
        "seconds": round(seconds, 2),
    }


def summarise(rows):
    n = len(rows)
    return {
        "n": n,
        "validated_first_attempt": sum(r["validated"] and r["attempts"] == 1 for r in rows),
        "validated_after_retry": sum(r["validated"] and r["attempts"] == 2 for r in rows),
        "fallback": sum(r["fallback_used"] for r in rows),
        "answers_with_citations": sum(r["n_cited"] > 0 for r in rows),
        "flagged_needs_human_review": sum(bool(r["needs_human_review"]) for r in rows),
        "median_confidence": statistics.median(r["confidence"] for r in rows if r["confidence"] is not None),
        "median_seconds": statistics.median(r["seconds"] for r in rows),
    }


ask_rows = []
for q in questions:
    t = time.perf_counter()
    resp, _ = qa_service.answer_with_template(q["question"], top_k=5)
    if resp.structured_meta.mode != "llm":
        sys.exit(f"{q['id']}: LLM call failed and fell back to retrieval-only; check the backend.")
    ask_rows.append(row(q["id"], resp.structured_meta, resp.structured, time.perf_counter() - t, q["primary_doc"]))
    print("ask  ", ask_rows[-1])


async def run_agent_all():
    out = []
    for q in questions:
        t = time.perf_counter()
        res = await agent_service.run_agent(q["question"])
        if res.structured_meta is None or res.structured_meta.mode != "llm":
            sys.exit(f"{q['id']}: agent LLM call failed: {res.answer[:200]}")
        r = row(q["id"], res.structured_meta, res.structured, time.perf_counter() - t)
        r["tools"] = [tc.tool for tc in res.tool_calls]
        out.append(r)
        print("agent", r)
    return out


agent_rows = asyncio.run(run_agent_all())

result = {
    "provider": resolved.provider,
    "model": resolved.model,
    "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "ask": {"summary": summarise(ask_rows), "rows": ask_rows},
    "agent": {"summary": summarise(agent_rows), "rows": agent_rows},
}
out = ROOT / "bench" / "structured_output_results.json"
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k]["summary"] for k in ("ask", "agent")}, indent=2))
print(f"Saved {out.relative_to(ROOT)}")
