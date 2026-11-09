"""
Live check of the MongoDB conversation history.

Runs the 21 labeled agent questions (bench/agent_tool_questions.json) through the
real POST /agent endpoint with the configured LLM, grouped into one session per
category, then reads everything back through GET /history/... and checks that
MongoDB holds exactly what the API returned.

    docker run -d --name rag-mongo -p 27017:27017 mongo:7
    MONGODB_URI=mongodb://localhost:27017 MONGODB_DB=rag_history_check python bench/history_live_check.py

Writes bench/history_live_results.json. Needs an LLM backend in .env.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.conversation_store import get_store  # noqa: E402
from app.main import app  # noqa: E402

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent / "data" / "sample_docs"


def main() -> None:
    if not settings.MONGODB_URI:
        sys.exit("Set MONGODB_URI first.")
    store = get_store()
    store._col.drop()  # a clean collection, so the counts below are this run only
    questions = json.loads((HERE / "agent_tool_questions.json").read_text())["questions"]
    run = datetime.now().strftime("%Y%m%d-%H%M%S")
    responses = []
    with TestClient(app) as client:
        for f in sorted(SAMPLES.iterdir()):
            with open(f, "rb") as fh:
                client.post("/ingest", files={"file": (f.name, fh, "text/plain")})
        if client.get("/health").json().get("llm_available") is not True:
            sys.exit("No LLM backend configured; the agent would not make real decisions.")
        for q in questions:
            sid = f"{run}-{q['category']}"
            t0 = time.perf_counter()
            r = client.post("/agent", json={"query": q["question"], "session_id": sid})
            if r.status_code == 400:  # blocked by Content Safety; the route still saves the turn
                responses.append({"id": q["id"], "session_id": sid, "turn_id": None, "tools": [],
                                  "blocked": r.json()["detail"], "seconds": round(time.perf_counter() - t0, 2)})
                print(q["id"], q["category"], "BLOCKED", r.json()["detail"])
                continue
            r.raise_for_status()
            body = r.json()
            responses.append({"id": q["id"], "session_id": sid, "turn_id": body["turn_id"],
                              "tools": [c["tool"] for c in body["tool_calls"]],
                              "expected": q["expected_tools"], "seconds": round(time.perf_counter() - t0, 2)})
            print(q["id"], q["category"], [c["tool"].split(".")[-1] for c in body["tool_calls"]], body["turn_id"])

        sessions = sorted({r["session_id"] for r in responses})
        read_back = {s: client.get(f"/history/{s}").json() for s in sessions}
        stats = client.get("/history/stats").json()
        review = client.get("/history/review").json()

    by_turn = {t["turn_id"]: t for turns in read_back.values() for t in turns}
    blocked_saved = [t for turns in read_back.values() for t in turns if t["input_flagged"]]
    mismatches = [r["id"] for r in responses if r["turn_id"] is not None and (r["turn_id"] not in by_turn or [c["tool"] for c in by_turn[r["turn_id"]]["tool_calls"]] != r["tools"])]
    in_order = all([t["query"] for t in turns] == [q["question"] for q in questions
                                                  if f"{run}-{q['category']}" == s]
                    for s, turns in read_back.items())
    out = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "llm_provider": next((t["llm_provider"] for t in by_turn.values() if not t["input_flagged"]), None),
        "mongodb": "mongo:7 (Docker)",
        "turns_sent": len(responses),
        "turns_read_back": len(by_turn),
        "blocked_by_content_safety": [r["id"] for r in responses if r.get("blocked")],
        "blocked_turns_saved": len(blocked_saved),
        "trace_mismatches": mismatches,
        "sessions": len(sessions),
        "sessions_in_order": in_order,
        "stats": stats,
        "review_queue": [{"query": t["query"], "reasons": t["review_reasons"]} for t in review],
        "rows": responses,
    }
    (HERE / "history_live_results.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2, default=str))


if __name__ == "__main__":
    main()
