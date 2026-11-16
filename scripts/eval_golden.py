"""Phase 5: evaluate the whole agent on the golden set (25 questions).

For every question the agent runs for real and we record what it did. Then:

  Tool choice      did it call the tools we expected?
  Retrieval        Precision and Recall of the documents its searches returned
  Facts (strings)  the answer contains the key facts and none of the forbidden ones
  Safety           paused before changing data; database still in the expected state
  LLM-as-judge     a second model reads question + reference + evidence + answer and
                   marks it correct / grounded, with a reason
  Latency, tokens  per question, plus which model answered

Everything is saved as it goes (data/cache/golden_runs.json and golden_judge.json).
The free Gemini tier allows only a few dozen requests per day, so one run may not
finish: run the script again later and it continues from where it stopped.

Run: python scripts/eval_golden.py            (run what is missing, then report)
     python scripts/eval_golden.py --report   (only rebuild the report from saved runs)
"""
import asyncio
import json
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain.chat_models import init_chat_model  # noqa: E402
from langchain_core.callbacks import UsageMetadataCallbackHandler  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from shopmind.agent import build_agent, run_turn  # noqa: E402
from shopmind.config import AGENT_FALLBACKS, AGENT_MODEL, CACHE_DIR, DB_PATH  # noqa: E402
from shopmind.tools import UserContext, get_retriever  # noqa: E402

GOLDEN = json.loads((ROOT / "data" / "eval" / "golden_set.json").read_text(encoding="utf-8"))
RUNS_FILE = CACHE_DIR / "golden_runs.json"
JUDGE_FILE = CACHE_DIR / "golden_judge.json"
REPORT_FILE = ROOT / "reports" / "golden_eval.md"
TITLE = "Golden set evaluation (Phase 5)"

# --after-fixes d8,u2,...  re-runs only those questions with the current agent and keeps the
# results apart from the first run, so "before" and "after" can be compared honestly.
if "--after-fixes" in sys.argv:
    ids = sys.argv[sys.argv.index("--after-fixes") + 1].split(",")
    GOLDEN = [q for q in GOLDEN if q["id"] in ids]
    RUNS_FILE = CACHE_DIR / "golden_runs_after_fixes.json"
    JUDGE_FILE = CACHE_DIR / "golden_judge_after_fixes.json"
    REPORT_FILE = ROOT / "reports" / "golden_eval_after_fixes.md"
    TITLE = "Golden set: re-run of selected questions after the fixes"
# --full-rerun  runs all 25 questions again with the current agent, kept apart from the first run.
if "--full-rerun" in sys.argv:
    RUNS_FILE = CACHE_DIR / "golden_runs_v2.json"
    JUDGE_FILE = CACHE_DIR / "golden_judge_v2.json"
    REPORT_FILE = ROOT / "reports" / "golden_eval_v2.md"
    TITLE = "Golden set: full re-run with the fixed agent"
PAUSE = 8          # seconds between questions (requests-per-minute limit)
JUDGE_BATCH = 5    # answers per judge request, to save quota
CONTEXTS = {"customer": UserContext("customer", "Khaled Zaki", 20), "staff": UserContext("staff", "Mona (store manager)")}
DOC_ID = re.compile(r"\[((?:POL|FAQ|SM)-[A-Z0-9-]+)\]")


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ 1. run the agent
async def run_question(agent, q) -> dict:
    usage = UsageMetadataCallbackHandler()
    run = {"tools": [], "tool_results": [], "retrieved": [], "answer": None, "route": None, "sources": [],
           "model": None, "paused": False}
    ctx, thread = CONTEXTS[q["role"]], f"golden-{q['id']}-{time.time():.0f}"
    start = time.perf_counter()

    async def consume(user_input):
        async for ev in run_turn(agent, user_input, thread, ctx, callbacks=[usage], tags=["golden", q["id"]]):
            if ev["type"] == "tool_call":
                run["tools"].append({"name": ev["name"], "args": ev["args"]})
            elif ev["type"] == "tool_result":
                run["tool_results"].append({"name": ev["name"], "content": ev["content"][:2500]})
                if ev["name"] == "search_store_docs":
                    run["retrieved"] += [d for d in DOC_ID.findall(ev["content"]) if d not in run["retrieved"]]
            elif ev["type"] == "approval_needed":
                run["paused"] = True
            elif ev["type"] == "answer":
                r = ev["reply"]
                run.update(answer=r.answer, route=r.route, sources=r.sources, model=ev["model"])

    await consume(q["question"])
    if run["paused"]:
        decision = {"type": "approve"} if q.get("on_pause") == "approve" else \
                   {"type": "reject", "message": "The human reviewer rejected this action."}
        run["decision"] = decision["type"]
        await consume(decision)

    run["latency_s"] = round(time.perf_counter() - start, 1)
    run["input_tokens"] = sum(u.get("input_tokens", 0) for u in usage.usage_metadata.values())
    run["output_tokens"] = sum(u.get("output_tokens", 0) for u in usage.usage_metadata.values())
    run["llm_calls_by_model"] = {m: 1 for m in usage.usage_metadata}  # models that answered at least once
    if "db_check" in q:
        con = sqlite3.connect(DB_PATH)
        run["db_status"] = con.execute("SELECT status FROM orders WHERE order_id = ?", (q["db_check"]["order_id"],)).fetchone()[0]
        con.close()
    if run["answer"] is None:
        raise RuntimeError("the agent finished without an answer")
    return run


async def run_missing() -> None:
    runs = load(RUNS_FILE)
    todo = [q for q in GOLDEN if q["id"] not in runs]
    if not todo:
        return
    agent = await build_agent()
    failures = 0
    for q in todo:
        try:
            runs[q["id"]] = await run_question(agent, q)
            save(RUNS_FILE, runs)
            print(f"  {q['id']} ok ({runs[q['id']]['latency_s']} s, {runs[q['id']]['model']})")
            failures = 0
        except Exception as e:
            failures += 1
            print(f"  {q['id']} failed: {type(e).__name__}: {str(e)[:100]}")
            if failures >= 2:
                print("  Two failures in a row: Gemini's free limit is probably used up. Stopping; run again later.")
                break
        await asyncio.sleep(PAUSE)
    get_retriever().close()


# ------------------------------------------------------------------ 2. LLM-as-judge
class Verdict(BaseModel):
    id: str
    correct: bool = Field(description="The answer agrees with the reference on every important fact, "
                                      "or correctly refuses when the reference says it must refuse")
    grounded: bool = Field(description="Every fact in the answer appears in the evidence (tool results). "
                                       "True for a refusal that states no facts")
    reason: str = Field(description="One short sentence explaining the marks")


class Verdicts(BaseModel):
    verdicts: list[Verdict]


JUDGE_PROMPT = """You are grading a customer-support assistant for an electronics store. Be strict and fair.

For each item you get: the question, a reference answer written by a human, the evidence the assistant
saw (tool results), and the assistant's answer. Give two independent marks:

- correct: does the answer agree with the reference on the important facts? Extra true details are fine.
  A missing key fact, a wrong number, or answering when the reference says to refuse = false.
  The answer may be in Arabic or English; judge the meaning, not the language.
- grounded: is every fact in the answer supported by the evidence? Anything not in the evidence = false.
  Greeting the user by the name given in "Asked by" is not an invented fact.

Return one verdict per item, using the same ids.

{items}"""


def judge_missing(runs: dict) -> None:
    verdicts = load(JUDGE_FILE)
    todo = [q for q in GOLDEN if q["id"] in runs and q["id"] not in verdicts]
    if not todo:
        return
    models = [init_chat_model(f"google_genai:{m}", temperature=0, max_retries=1, timeout=90)
              .with_structured_output(Verdicts) for m in [AGENT_MODEL, *AGENT_FALLBACKS]]
    judge = models[0].with_fallbacks(models[1:])
    for i in range(0, len(todo), JUDGE_BATCH):
        batch = todo[i:i + JUDGE_BATCH]
        items = []
        for q in batch:
            r = runs[q["id"]]
            evidence = "\n".join(f"({t['name']}) {t['content'][:1500]}" for t in r["tool_results"]) or "(no tool was called)"
            who = CONTEXTS[q["role"]]   # the judge marked "Hi Mona" as invented: tell it who is asking
            items.append(f"### id: {q['id']}\nAsked by: {who.name} ({who.role})\n"
                         f"Question: {q['question']}\nReference: {q['reference']}\n"
                         f"Evidence:\n{evidence}\nAssistant's answer: {r['answer']}")
        try:
            out = judge.invoke(JUDGE_PROMPT.format(items="\n\n".join(items)))
        except Exception as e:
            print(f"  judge failed: {type(e).__name__}: {str(e)[:100]}. Run again later to finish judging.")
            break
        for v in out.verdicts:
            if any(q["id"] == v.id for q in batch):
                verdicts[v.id] = v.model_dump()
        save(JUDGE_FILE, verdicts)
        print(f"  judged {', '.join(q['id'] for q in batch)}")
        time.sleep(PAUSE)


# ------------------------------------------------------------------ 3. grade and report
def grade(q: dict, r: dict) -> dict:
    called = [t["name"] for t in r["tools"]]
    text = r["answer"].replace(",", "").lower()   # "Liquid" must match "liquid": found in the full re-run
    g = {"tool_ok": set(q["expected_tools"]) <= set(called)}
    g["facts_ok"] = (all(f.replace(",", "").lower() in text for f in q.get("must_include", []))
                     and not any(f.replace(",", "").lower() in text for f in q.get("must_not_include", [])))
    if q["relevant_docs"]:
        retrieved = set(r["retrieved"])  # a document can come back as several chunks: count it once
        hit = retrieved & set(q["relevant_docs"])
        g["recall"] = len(hit) / len(q["relevant_docs"])
        g["precision"] = len(hit) / len(retrieved) if retrieved else 0.0
    if q.get("expect_pause"):
        g["pause_ok"] = r["paused"]
    if "db_check" in q:
        g["db_ok"] = r.get("db_status") == q["db_check"]["status"]
    has_arabic = bool(re.search("[؀-ۿ]", r["answer"]))
    g["lang_ok"] = has_arabic if q.get("language") == "ar" else not has_arabic
    return g


def frac(values) -> str:
    values = list(values)
    return f"{sum(values)}/{len(values)}" if values else "-"


def report() -> None:
    runs, verdicts = load(RUNS_FILE), load(JUDGE_FILE)
    done = [q for q in GOLDEN if q["id"] in runs]
    grades = {q["id"]: grade(q, runs[q["id"]]) for q in done}
    L = [f"# {TITLE}", "",
         f"**{len(done)} of {len(GOLDEN)} questions run**, {sum(q['id'] in verdicts for q in done)} judged. "
         "Each question went through the real agent (tools, MCP, memory, human approval)."]
    if len(done) < len(GOLDEN):
        missing = ", ".join(q["id"] for q in GOLDEN if q["id"] not in runs)
        L += ["", f"> Not run yet (Gemini's free daily limit): {missing}. Run `python scripts/eval_golden.py` again to continue."]
    if not done:
        REPORT_FILE.write_text("\n".join(L) + "\n", encoding="utf-8")
        return

    G = list(grades.values())
    judged = [verdicts[q["id"]] for q in done if q["id"] in verdicts]
    lat = sorted(runs[q["id"]]["latency_s"] for q in done)
    p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))]
    L += ["", "## Summary", "", "| Metric | Result | What it means |", "|---|---|---|",
          f"| Right tool chosen | {frac(g['tool_ok'] for g in G)} | called every tool we expected |",
          f"| Key facts present (string check) | {frac(g['facts_ok'] for g in G)} | required facts in, forbidden facts out |",
          f"| Correct (LLM judge) | {frac(v['correct'] for v in judged)} | agrees with the human reference answer |",
          f"| Grounded (LLM judge) | {frac(v['grounded'] for v in judged)} | every fact is in the tool results |",
          f"| Retrieval Recall | {statistics.mean(g['recall'] for g in G if 'recall' in g):.2f} | share of the relevant documents the agent's searches returned |",
          f"| Retrieval Precision | {statistics.mean(g['precision'] for g in G if 'precision' in g):.2f} | share of returned documents that were relevant |",
          f"| Paused before changing data | {frac(g['pause_ok'] for g in G if 'pause_ok' in g)} | human-in-the-loop fired |",
          f"| Database in the expected state | {frac(g['db_ok'] for g in G if 'db_ok' in g)} | nothing changed that should not |",
          f"| Replied in the user's language | {frac(g['lang_ok'] for g in G)} | Arabic for Arabic, English for English |",
          f"| Latency | median {statistics.median(lat):.1f} s, p95 {p95:.1f} s, max {lat[-1]:.1f} s | whole turn, all model and tool calls |",
          f"| Tokens per question | {statistics.mean(runs[q['id']]['input_tokens'] for q in done):.0f} in / "
          f"{statistics.mean(runs[q['id']]['output_tokens'] for q in done):.0f} out | average, all model calls of the turn |"]

    types = list(dict.fromkeys(q["type"] for q in GOLDEN))
    L += ["", "## By question type", "", "| Type | Run | Right tool | Facts (string) | Correct (judge) | Grounded (judge) | Median latency |",
          "|---|---|---|---|---|---|---|"]
    for t in types:
        qs = [q for q in done if q["type"] == t]
        if not qs:
            L.append(f"| {t} | 0 | - | - | - | - | - |")
            continue
        vs = [verdicts[q["id"]] for q in qs if q["id"] in verdicts]
        L.append(f"| {t} | {len(qs)} | {frac(grades[q['id']]['tool_ok'] for q in qs)} | {frac(grades[q['id']]['facts_ok'] for q in qs)} | "
                 f"{frac(v['correct'] for v in vs)} | {frac(v['grounded'] for v in vs)} | "
                 f"{statistics.median(runs[q['id']]['latency_s'] for q in qs):.1f} s |")

    models = {}
    for q in done:
        models[runs[q["id"]]["model"]] = models.get(runs[q["id"]]["model"], 0) + 1
    L += ["", "## Which model answered", "",
          "The agent tries the main model first and falls back when it fails or its free quota is used up.", ""]
    L += [f"- `{m}`: {n} questions" for m, n in sorted(models.items(), key=lambda x: -x[1])]

    L += ["", "## Every question", "", "| id | Type | Tools called | Tool | Facts | Judge: correct | Judge: grounded | Lang | Latency | Model |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    mark = lambda b: "✅" if b else "❌"  # noqa: E731
    for q in done:
        r, g, v = runs[q["id"]], grades[q["id"]], verdicts.get(q["id"])
        L.append(f"| {q['id']} | {q['type']} | {', '.join(t['name'] for t in r['tools']) or 'none'} | {mark(g['tool_ok'])} | "
                 f"{mark(g['facts_ok'])} | {mark(v['correct']) if v else '-'} | {mark(v['grounded']) if v else '-'} | "
                 f"{mark(g['lang_ok'])} | {r['latency_s']} s | {r['model'].replace('gemini-', '')} |")

    L += ["", "## Problems", ""]
    problems = 0
    for q in done:
        r, g, v = runs[q["id"]], grades[q["id"]], verdicts.get(q["id"])
        issues = [n for k, n in [("tool_ok", "expected tool not called"), ("facts_ok", "string check failed"),
                                 ("pause_ok", "did not pause"), ("db_ok", "database changed"), ("lang_ok", "wrong language")]
                  if k in g and not g[k]]
        if v and not v["correct"]:
            issues.append("judge: not correct")
        if v and not v["grounded"]:
            issues.append("judge: not grounded")
        if issues:
            problems += 1
            L += [f"**{q['id']} ({q['type']}): {q['question'][:110]}**", "",
                  f"- Issues: {', '.join(issues)}",
                  f"- Tools: {', '.join(t['name'] + ' ' + json.dumps(t['args'], ensure_ascii=False)[:120] for t in r['tools']) or 'none'}",
                  f"- Answer ({r['model']}): {r['answer'][:400]}"]
            if v:
                L.append(f"- Judge: {v['reason']}")
            L.append("")
    if not problems:
        L.append("None.")

    REPORT_FILE.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:34]))


if __name__ == "__main__":
    if "--report" not in sys.argv:
        print("Running the agent on missing questions...")
        asyncio.run(run_missing())
        print("Judging...")
        judge_missing(load(RUNS_FILE))
    report()
