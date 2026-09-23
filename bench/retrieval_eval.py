"""Score retrieval quality on the built-in benchmark questions.

For each question we know which document should answer it (primary_doc) and which
keywords a good answer passage should contain (expected_keywords). We ingest the four
sample documents into a temporary vector store, retrieve, and report:

  hit@k        - is at least one of the top-k chunks from the expected document?
  keyword cov. - fraction of expected keywords that appear in the top-3 chunks' text

Run:  python bench/retrieval_eval.py
"""
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp(prefix="rag_eval_")
os.environ["CHROMA_DB_PATH"] = os.path.join(tmp, "chroma")
os.environ["EXPERIMENTS_DB_PATH"] = os.path.join(tmp, "experiments.db")
sys.path.insert(0, str(ROOT))

from app.services import ingest_service, retrieval_service  # noqa: E402

for doc in sorted((ROOT / "data" / "sample_docs").iterdir()):
    ingest_service.ingest_file(str(doc), original_filename=doc.name)

questions = json.loads((ROOT / "tests" / "benchmark_questions.json").read_text())["questions"]

MODES = {
    "semantic": dict(use_hybrid=False),
    "hybrid (alpha 0.7)": dict(use_hybrid=True, hybrid_alpha=0.7),
    "hybrid (alpha 0.5)": dict(use_hybrid=True, hybrid_alpha=0.5),
    "keyword-heavy (alpha 0.2)": dict(use_hybrid=True, hybrid_alpha=0.2),
}

results = {}
misses = {}
for name, kwargs in MODES.items():
    hits = {1: 0, 3: 0, 5: 0}
    coverage = []
    missed = []
    for q in questions:
        chunks = retrieval_service.retrieve(q["question"], top_k=5, **kwargs)
        for k in hits:
            if any(c.doc_name.startswith(q["primary_doc"]) for c in chunks[:k]):
                hits[k] += 1
        text = " ".join(c.text.lower() for c in chunks[:3])
        kws = q["expected_keywords"]
        coverage.append(sum(kw.lower() in text for kw in kws) / len(kws))
        if not any(c.doc_name.startswith(q["primary_doc"]) for c in chunks[:5]):
            missed.append(q["id"])
    n = len(questions)
    results[name] = {
        "n_questions": n,
        "hit@1": round(hits[1] / n, 3),
        "hit@3": round(hits[3] / n, 3),
        "hit@5": round(hits[5] / n, 3),
        "keyword_coverage_top3": round(statistics.mean(coverage), 3),
    }
    misses[name] = missed

print(f"{'mode':28} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'kw cov (top3)':>14}")
for name, r in results.items():
    print(f"{name:28} {r['hit@1']:>6} {r['hit@3']:>6} {r['hit@5']:>6} {r['keyword_coverage_top3']:>14}")
print("\nquestions with no expected-document chunk in the top 5:")
for name, m in misses.items():
    print(f"  {name}: {m or 'none'}")
(ROOT / "bench" / "retrieval_eval_results.json").write_text(json.dumps({"results": results, "missed_top5": misses}, indent=2))
