"""Measure work-order field extraction against the labeled PDFs.

For each of the 14 PDFs in bench/extraction/docs it runs the real /extract
pipeline (PDF text -> structured output -> validation against the document ->
one retry -> fallback) and compares the result with bench/extraction/labels.json,
field by field: equipment_id, work_date, technician, parts (name and quantity),
downtime_hours and status.

It also scores the model's first raw reply before validation, so the effect of
the validation step is visible: how many wrong values it rejected, and whether
the documents that still came out wrong were flagged for human review.

Backends:
  --backend azure    the Azure OpenAI deployment from .env (default)
  --backend ollama   a local model through Ollama's OpenAI-compatible API (--model)

Run:  python bench/extraction_eval.py --backend azure
      python bench/extraction_eval.py --backend ollama --model qwen2.5:7b
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import extraction_service as ex  # noqa: E402
from app.utils.file_loader import load_file  # noqa: E402

DOCS = ROOT / "bench" / "extraction" / "docs"
LABELS = json.loads((ROOT / "bench" / "extraction" / "labels.json").read_text())
SETS = {
    "tuning": ("docs", "labels.json"),     # the 14 PDFs the field descriptions were tuned on
    "heldout": ("docs_heldout", "labels_heldout.json"),  # 6 PDFs written after tuning
}
FIELDS = ["equipment_id", "work_date", "technician", "parts", "downtime_hours", "status"]


def squash(v):
    return None if v is None else re.sub(r"[^a-z0-9]", "", str(v).lower())


def parts_match(pred, gold) -> bool:
    if len(pred) != len(gold):
        return False
    left = list(pred)
    for key, qty in gold:
        hit = next((p for p in left if key.lower().rstrip("s") in p["name"].lower() and p["quantity"] == qty), None)
        if hit is None:
            return False
        left.remove(hit)
    return True


def field_ok(name, pred, gold) -> bool:
    if name == "parts":
        return parts_match(pred or [], gold)
    if name == "downtime_hours":
        return (pred is None and gold is None) or (pred is not None and gold is not None and abs(float(pred) - gold) < 0.01)
    return squash(pred) == squash(gold)


def invented(name, pred, gold) -> bool:
    """A value given where the document states none."""
    if name == "parts":
        return not gold and bool(pred)
    return gold is None and pred is not None


def make_client(backend: str, model: str):
    if backend == "azure":
        from app.services import llm_service

        client, deployment, provider = llm_service.get_chat_client()
        if provider != "azure_openai":
            sys.exit("Azure OpenAI is not configured in .env.")
        return client, deployment
    from openai import OpenAI

    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), model


def run(backend: str, model: str, docs=DOCS, labels=LABELS) -> dict:
    client, model = make_client(backend, model)
    rows = []
    for pdf in sorted(docs.glob("*.pdf")):
        gold = labels[pdf.name]
        text, _ = load_file(pdf)
        raws = []

        def call(feedback, _text=text):
            msgs = ex.build_messages(_text)
            if feedback:
                msgs.append({"role": "user", "content": feedback})
            r = client.chat.completions.create(model=model, messages=msgs, temperature=0, response_format=ex.RESPONSE_FORMAT)
            raws.append(r.choices[0].message.content or "")
            return raws[-1]

        start = time.perf_counter()
        fields, meta = ex.generate(call, text)
        seconds = time.perf_counter() - start
        final = fields.model_dump()
        try:
            first = json.loads(raws[0])
        except (ValueError, IndexError):
            first = {}
        rows.append({
            "doc": pdf.name,
            "validated": meta.validated,
            "attempts": meta.attempts,
            "fallback": meta.fallback_used,
            "errors": meta.errors,
            "needs_human_review": final["needs_human_review"],
            "seconds": round(seconds, 2),
            "final_ok": {f: field_ok(f, final.get(f), gold[f]) for f in FIELDS},
            "first_ok": {f: field_ok(f, first.get(f), gold[f]) for f in FIELDS},
            "final_invented": [f for f in FIELDS if invented(f, final.get(f), gold[f])],
            "first_invented": [f for f in FIELDS if invented(f, first.get(f), gold[f])],
            "final": final,
            "first_reply": first,
        })

    n = len(rows)
    total = n * len(FIELDS)
    final_right = sum(sum(r["final_ok"].values()) for r in rows)
    first_right = sum(sum(r["first_ok"].values()) for r in rows)
    wrong_docs = [r for r in rows if not all(r["final_ok"].values())]
    first_rejected = [r for r in rows if r["attempts"] > 1 or r["fallback"]]
    rejected_with_wrong_value = [r for r in first_rejected if not all(r["first_ok"].values())]
    summary = {
        "backend": backend,
        "model": model,
        "documents": n,
        "field_accuracy": f"{final_right}/{total} ({100 * final_right / total:.1f}%)",
        "first_reply_field_accuracy": f"{first_right}/{total} ({100 * first_right / total:.1f}%)",
        "documents_fully_correct": f"{n - len(wrong_docs)}/{n}",
        "invented_values_final": sum(len(r["final_invented"]) for r in rows),
        "invented_values_first_reply": sum(len(r["first_invented"]) for r in rows),
        "valid_first_try": sum(1 for r in rows if r["validated"] and r["attempts"] == 1),
        "fixed_by_retry": sum(1 for r in rows if r["validated"] and r["attempts"] == 2),
        "fell_back_to_review": sum(1 for r in rows if r["fallback"]),
        "first_replies_rejected_that_had_a_wrong_value": f"{len(rejected_with_wrong_value)}/{len(first_rejected)}",
        "wrong_documents_flagged_for_review": f"{sum(1 for r in wrong_docs if r['needs_human_review'])}/{len(wrong_docs)}",
        "per_field_accuracy": {f: f"{sum(r['final_ok'][f] for r in rows)}/{n}" for f in FIELDS},
        "median_seconds": sorted(r["seconds"] for r in rows)[n // 2],
    }
    return {"summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["azure", "ollama"], default="azure")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--set", choices=list(SETS), default="tuning")
    args = ap.parse_args()
    folder, label_file = SETS[args.set]
    base = ROOT / "bench" / "extraction"
    result = run(args.backend, args.model, base / folder, json.loads((base / label_file).read_text()))
    result["summary"]["set"] = args.set
    tag = ("azure" if args.backend == "azure" else args.model.replace(":", "_")) + ("_heldout" if args.set == "heldout" else "")
    out = ROOT / "bench" / f"extraction_results_{tag}.json"
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result["summary"], indent=1))
    for r in result["rows"]:
        bad = [f for f, ok in r["final_ok"].items() if not ok]
        if bad or r["attempts"] > 1:
            print(r["doc"], "wrong:", bad, "attempts:", r["attempts"], "review:", r["needs_human_review"], r["errors"][:2])
    print("wrote", out)


if __name__ == "__main__":
    main()
