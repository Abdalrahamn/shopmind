"""Phase 4 demo: the agent answers the project's demo questions, streamed step by step.

Each scene shows one skill:
  1. documents (RAG)            a policy question
  2. database (SQL)             top customers, asked by staff
  3. role check                 a customer asks for the same business data
  4. documents + filter + MCP   a phone under a budget that is in stock,
     then memory                a follow-up that only makes sense after it
  5. human-in-the-loop          cancel an order: the agent pauses, we approve

Finished scenes are saved in data/cache/agent_demo_scenes.json and reused on the next run.

The transcript is saved to reports/agent_demo.md.
Uses about 13 Gemini requests. Run: python scripts/demo_agent.py
"""
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopmind.agent import build_agent, run_turn  # noqa: E402
from shopmind.config import DB_PATH  # noqa: E402
from shopmind.tools import UserContext, get_retriever  # noqa: E402

SCENES_FILE = ROOT / "data" / "cache" / "agent_demo_scenes.json"
PAUSE = 12  # seconds between scenes, to stay under the free tier's requests-per-minute limit
lines: list[str] = []


def log(text: str = "") -> None:
    print(text)
    lines.append(text)


async def turn(agent, text, thread, ctx, label=None):
    if label:
        log(f"\n**{ctx.name} ({ctx.role}):** {label}\n")
    start = time.perf_counter()
    paused = False
    async for ev in run_turn(agent, text, thread, ctx):
        if ev["type"] == "tool_call":
            log(f"- 🔧 calls `{ev['name']}` with `{json.dumps(ev['args'], ensure_ascii=False)}`")
        elif ev["type"] == "tool_result":
            short = ev["content"].replace("\n", " ")
            log(f"- 📥 `{ev['name']}` returned: {short[:230]}{'…' if len(short) > 230 else ''}")
        elif ev["type"] == "approval_needed":
            paused = True
            log(f"- ⏸️ **paused for approval:** `{ev['name']}` with `{json.dumps(ev['args'])}`")
        elif ev["type"] == "answer":
            r = ev["reply"]
            log(f"\n**ShopMind:** {r.answer}\n")
            log(f"*route: {r.route} · sources: {', '.join(r.sources) or 'none'} · "
                f"{time.perf_counter() - start:.1f} s · answered by {ev['model']}*")
    return paused


async def scene(key: str, title: str, play) -> None:
    """Run one scene. Finished scenes are saved, so a re-run (for example after
    the daily Gemini limit is hit) continues from the first unfinished scene."""
    global lines
    done = json.loads(SCENES_FILE.read_text(encoding="utf-8")) if SCENES_FILE.exists() else {}
    if key in done:
        print(f"(scene {key} already done, reusing saved transcript)")
        lines += done[key]
        return
    before = len(lines)
    log(f"\n## {title}")
    try:
        await play()
    except Exception as e:
        del lines[before:]
        print(f"Scene {key} failed: {type(e).__name__}: {str(e)[:150]}")
        lines.append(f"\n## {title}\n\n*Not run yet: Gemini's free daily limit was reached. Run the demo again later.*")
        return
    done[key] = lines[before:]
    SCENES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCENES_FILE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    await asyncio.sleep(PAUSE)


async def main() -> None:
    con = sqlite3.connect(DB_PATH)
    order_id, cid, name = con.execute(
        """SELECT o.order_id, c.customer_id, c.full_name FROM orders o JOIN customers c USING (customer_id)
           WHERE o.status = 'pending' ORDER BY o.order_id LIMIT 1""").fetchone()
    con.close()
    customer = UserContext("customer", name, cid)
    staff = UserContext("staff", "Mona (store manager)")

    agent = await build_agent()
    log("# Agent demo (Phase 4)\n")
    log("Every step below was streamed live while the agent worked.")

    async def s1():
        q = "how long do I have to return something I opened?"
        await turn(agent, q, "t1", customer, q)

    async def s2():
        q = "who are our top 5 customers by total spending?"
        await turn(agent, q, "t2", staff, q)

    async def s3():
        q = "who are your top 5 customers by total spending?"
        await turn(agent, q, "t3", customer, q)

    async def s45():
        q = "عايز موبايل تحت 15 الف ويكون متوفر دلوقتي"
        await turn(agent, q, "t4", customer, q)
        await asyncio.sleep(PAUSE)
        log("\n### Follow-up in the same conversation → memory")
        await turn(agent, "وضمانه قد ايه؟", "t4", customer, "وضمانه قد ايه؟")

    async def s6():
        q = f"please cancel my order {order_id}"
        paused = await turn(agent, q, "t5", customer, q)
        if not paused:
            raise RuntimeError("the agent did not pause for approval")
        con = sqlite3.connect(DB_PATH)
        before = con.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,)).fetchone()[0]
        log(f"\nWhile paused, order {order_id} is still `{before}` in the database. A human now approves.\n")
        await turn(agent, {"type": "approve"}, "t5", customer)
        after = con.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,)).fetchone()[0]
        con.close()
        log(f"\nAfter approval, order {order_id} is `{after}` in the database.")

    await scene("1", "1. A policy question → documents (RAG)", s1)
    await scene("2", "2. A numbers question from staff → database (SQL)", s2)
    await scene("3", "3. The same question from a customer → refused (dynamic prompt + code check)", s3)
    await scene("4", "4. Product advice with a budget and stock → documents + filter + MCP, then memory", s45)
    await scene("6", "5. Cancel an order → human-in-the-loop", s6)

    (ROOT / "reports" / "agent_demo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    get_retriever().close()


if __name__ == "__main__":
    asyncio.run(main())
