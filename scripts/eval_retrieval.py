"""Phase 2 evaluation: which retrieval setup finds the right documents?

For every labeled question we know which documents hold the answer. Each
setup returns its top documents and we measure:

  Precision@K  share of the top K results that are relevant
  Recall@K     share of the relevant documents that appear in the top K
  MRR          1 / rank of the first relevant result, averaged (1.0 = always first)

Results are printed and saved to reports/retrieval_eval.md.

Run: python scripts/eval_retrieval.py            (all setups, uses Gemini for rewriting)
     python scripts/eval_retrieval.py --no-llm   (skip the setups that call Gemini)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopmind.retrieval import Retriever  # noqa: E402

QUERIES = json.loads((ROOT / "data" / "eval" / "retrieval_queries.json").read_text(encoding="utf-8"))
K = 3

SETUPS = [
    # name,                   method,            rerank, rewrite
    ("TF-IDF (scratch)",       "tfidf",           False, False),
    ("BM25 (scratch)",         "bm25_scratch",    False, False),
    ("BM25 (Weaviate)",        "bm25",            False, False),
    ("Semantic",               "semantic",        False, False),
    ("Hybrid RRF",             "hybrid",          False, False),
    ("Hybrid (Weaviate)",      "weaviate_hybrid", False, False),
    ("Hybrid RRF + rerank",    "hybrid",          True,  False),
    ("Rewrite + Hybrid RRF",   "hybrid",          False, True),
    ("Rewrite + Hybrid + rerank", "hybrid",       True,  True),
]


def metrics(ranked: list[str], relevant: set[str], k: int) -> dict:
    top = ranked[:k]
    hits = [d in relevant for d in top]
    first = next((i for i, d in enumerate(ranked, 1) if d in relevant), None)
    return {"p": sum(hits) / k, "r": sum(hits) / len(relevant), "mrr": 1 / first if first else 0.0}


def main(use_llm: bool) -> None:
    setups = [s for s in SETUPS if use_llm or not s[3]]
    results = {}  # setup -> list of per-question rows

    rewritten = {q["id"] for q in QUERIES}
    with Retriever() as retriever:
        if use_llm:
            print("Rewriting questions with Gemini (cached on disk, once per question)...")
            for q in QUERIES:
                try:
                    retriever.rewrite(q["question"])
                except Exception as e:  # usually the free tier's daily limit
                    print(f"  Gemini failed on {q['id']}: {type(e).__name__}")
                    rewritten.discard(q["id"])
            if len(rewritten) < len(QUERIES):
                # Compare fairly: plain hybrid on the same questions that have a rewrite.
                setups.append(("Hybrid RRF (same questions)", "hybrid", False, False))

        for name, method, rerank, rewrite in setups:
            subset = rewrite or name.endswith("(same questions)")
            questions = [q for q in QUERIES if q["id"] in rewritten] if subset else QUERIES
            start = time.perf_counter()
            rows = []
            for q in questions:
                hits = retriever.search(q["question"], method, k=10, rerank=rerank, rewrite=rewrite, unique_docs=True)
                ranked = [h.doc_id for h in hits]
                rows.append({"id": q["id"], "type": q["type"], "ranked": ranked,
                             **metrics(ranked, set(q["relevant"]), K)})
            ms = (time.perf_counter() - start) * 1000 / len(questions)
            results[name] = {"rows": rows, "ms": ms}

    # ---------------------------------------------------------------- report
    def avg(rows, key):
        return sum(r[key] for r in rows) / len(rows)

    lines = ["# Retrieval evaluation (Phase 2)", "",
             f"{len(QUERIES)} labeled questions, document level, K = {K}. "
             "Archived documents are filtered out by default.", "",
             f"| Setup | Questions | Precision@{K} | Recall@{K} | MRR | ms / query |", "|---|---|---|---|---|---|"]
    for name, res in results.items():
        rows = res["rows"]
        lines.append(f"| {name} | {len(rows)} | {avg(rows, 'p'):.2f} | {avg(rows, 'r'):.2f} | "
                     f"{avg(rows, 'mrr'):.2f} | {res['ms']:.0f} |")
    if len(rewritten) < len(QUERIES):
        missing = ", ".join(q["id"] for q in QUERIES if q["id"] not in rewritten)
        lines += ["", f"> Gemini's free daily limit was reached, so the rewrite setups ran on {len(rewritten)} "
                  f"questions only (missing: {missing}). Compare them with *Hybrid RRF (same questions)*. "
                  "Rewrites are cached, so the next run only asks Gemini for the missing ones."]

    types = sorted({q["type"] for q in QUERIES})
    lines += ["", f"## Recall@{K} by question type", "",
              "| Setup | " + " | ".join(types) + " |", "|---" * (len(types) + 1) + "|"]
    for name, res in results.items():
        cells = []
        for t in types:
            rows = [r for r in res["rows"] if r["type"] == t]
            cells.append(f"{avg(rows, 'r'):.2f}" if rows else "-")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", f"## Misses (no relevant document in the top {K})", ""]
    for name, res in results.items():
        missed = [r for r in res["rows"] if r["r"] == 0]
        if missed:
            detail = ", ".join(f"{r['id']} (got {', '.join(r['ranked'][:K]) or 'nothing'})" for r in missed)
            lines.append(f"- **{name}** ({len(missed)}): {detail}")

    report = "\n".join(lines) + "\n"
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "retrieval_eval.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main(use_llm="--no-llm" not in sys.argv)
