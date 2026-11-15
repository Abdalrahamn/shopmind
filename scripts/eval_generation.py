"""Phase 3 evaluation: are the answers correct, grounded and honest?

Part 1 compares two Gemini models on 10 questions (7 answerable, 3 not):
  Facts correct     the answer contains the key facts and none of the wrong ones
  Refusals correct  says "I don't know" exactly when the sources have no answer
  Citations         cited documents are the relevant ones; none are made up
  Language          Arabic questions get Arabic answers
  Latency, tokens   cost side of the comparison

Part 2 is a sampling test: the same question three times at temperature 0
and three times at a high temperature, to see how much the answer changes.

Every answer is cached in data/cache/answers.json (the free Gemini tier
allows about 20 requests per model per day), so a re-run costs nothing.

Run: python scripts/eval_generation.py
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopmind.config import GEMINI_MODEL, REWRITE_MODEL  # noqa: E402
from shopmind.generation import Generator  # noqa: E402
from shopmind.retrieval import Retriever  # noqa: E402

QUESTIONS = json.loads((ROOT / "data" / "eval" / "generation_questions.json").read_text(encoding="utf-8"))
MODELS = [GEMINI_MODEL, REWRITE_MODEL]          # the main model vs the cheaper "lite" one
SAMPLING_QUESTION = "can I return the Pixel 10a?"
TEMPERATURES = [0.0, 1.5]
RUNS = 3
PAUSE = 7                                       # seconds between live calls (free tier: few requests per minute)


def ask(gen: Generator, question: str, run: int = 0):
    try:
        res = gen.answer(question, run=run)
    except Exception as e:
        print(f"    {gen.model} failed: {type(e).__name__}: {str(e)[:90]}")
        return None
    if not res.cached:
        time.sleep(PAUSE)
    return res


def grade(q: dict, res) -> dict:
    text = res.answer.replace(",", "")  # so "3,000" and "3000" both count
    facts = (all(f.replace(",", "") in text for f in q.get("must_include", []))
             and not any(f.replace(",", "") in text for f in q.get("must_not_include", [])))
    row = {"id": q["id"], "type": q["type"], "refusal_ok": res.answerable == q["answerable"],
           "facts_ok": facts, "made_up": bool(res.dropped_citations), "res": res}
    if q["answerable"]:
        row["cites_ok"] = bool(res.citations) and set(res.citations) <= set(q["relevant"])
        row["cites_found"] = bool(set(res.citations) & set(q["relevant"]))
    # The reply must be in the customer's language: Arabic for Arabic questions, English otherwise.
    has_arabic = bool(re.search(r"[؀-ۿ]", res.answer))
    row["lang_ok"] = has_arabic if q.get("language") == "ar" else not has_arabic
    return row


def share(rows, key):
    vals = [r[key] for r in rows if key in r]
    return f"{sum(vals)}/{len(vals)}" if vals else "-"


def main() -> None:
    lines = ["# Generation evaluation (Phase 3)", "",
             f"{len(QUESTIONS)} questions: {sum(q['answerable'] for q in QUESTIONS)} answerable, "
             f"{sum(not q['answerable'] for q in QUESTIONS)} that the documents cannot answer. "
             "Retrieval is the Phase 2 default (rewrite + hybrid), 6 chunks, temperature 0.", ""]
    with Retriever() as retriever:
        # ------------------------------------------------ Part 1: models
        graded = {}
        for model in MODELS:
            print(f"Model {model}")
            gen = Generator(retriever, model=model, temperature=0.0)
            rows = []
            for q in QUESTIONS:
                res = ask(gen, q["question"])
                if res:
                    rows.append(grade(q, res))
            graded[model] = rows

        lines += ["## Model comparison", "",
                  "| Model | Answered | Facts correct | Refusals correct | Cites only relevant docs | Cites a relevant doc | "
                  "Made-up citations | Reply in customer's language | Avg latency | Avg tokens in / out |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for model, rows in graded.items():
            if not rows:
                lines.append(f"| {model} | 0/{len(QUESTIONS)} (quota) | - | - | - | - | - | - | - | - |")
                continue
            n = len(rows)
            lat = sum(r["res"].latency_s for r in rows) / n
            tin = sum(r["res"].input_tokens for r in rows) / n
            tout = sum(r["res"].output_tokens for r in rows) / n
            lines.append(f"| {model} | {n}/{len(QUESTIONS)} | {share(rows, 'facts_ok')} | {share(rows, 'refusal_ok')} | "
                         f"{share(rows, 'cites_ok')} | {share(rows, 'cites_found')} | {sum(r['made_up'] for r in rows)} | "
                         f"{share(rows, 'lang_ok')} | {lat:.1f} s | {tin:.0f} / {tout:.0f} |")

        lines += ["", "## Problems found", ""]
        problems = 0
        for model, rows in graded.items():
            for r in rows:
                issues = [name for key, name in [("facts_ok", "wrong or missing fact"), ("refusal_ok", "wrong refusal decision"),
                                                 ("cites_found", "no relevant citation"), ("lang_ok", "wrong language")]
                          if key in r and not r[key]]
                if r["made_up"]:
                    issues.append(f"made-up citation {r['res'].dropped_citations}")
                if issues:
                    problems += 1
                    lines.append(f"- **{model}**, {r['id']} ({r['type']}): {', '.join(issues)}. "
                                 f"Answer: \"{r['res'].answer[:220]}\"")
        if not problems:
            lines.append("None.")

        lines += ["", "## Answers", ""]
        for q in QUESTIONS:
            lines.append(f"**{q['id']} ({q['type']}): {q['question']}**")
            if q.get("note"):
                lines.append(f"*{q['note']}*")
            lines.append("")
            for model, rows in graded.items():
                r = next((r for r in rows if r["id"] == q["id"]), None)
                if r:
                    tag = "answered" if r["res"].answerable else "said it does not know"
                    lines.append(f"- `{model}` ({tag}; cites {', '.join(r['res'].citations) or 'nothing'}): {r['res'].answer}")
            lines.append("")

        # ------------------------------------------------ Part 2: sampling
        print("Sampling test")
        lines += ["## Sampling: temperature 0 vs high temperature", "",
                  f"Question: *{SAMPLING_QUESTION}* asked {RUNS} times per temperature with `{GEMINI_MODEL}`.", ""]
        for temp in TEMPERATURES:
            gen = Generator(retriever, model=GEMINI_MODEL, temperature=temp)
            answers = [r for r in (ask(gen, SAMPLING_QUESTION, run=i) for i in range(RUNS)) if r]
            if not answers:
                lines.append(f"**Temperature {temp}:** no answers (quota).")
                continue
            distinct = len({a.answer for a in answers})
            lengths = [len(a.answer.split()) for a in answers]
            correct = sum("defective" in a.answer and a.answerable for a in answers)
            lines.append(f"**Temperature {temp}:** {distinct} different wordings in {len(answers)} runs, "
                         f"{min(lengths)}–{max(lengths)} words, key fact correct in {correct}/{len(answers)}.")
            lines.append("")
            for i, a in enumerate(answers, 1):
                lines.append(f"{i}. {a.answer}")
            lines.append("")

    report = "\n".join(lines) + "\n"
    (ROOT / "reports" / "generation_eval.md").write_text(report, encoding="utf-8")
    print(report[:2600])


if __name__ == "__main__":
    main()
