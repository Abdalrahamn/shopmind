# Phase 4 findings and decisions

The full transcript of the demo is in [agent_demo.md](agent_demo.md)
(run `python scripts/demo_agent.py` to reproduce; finished scenes are cached).

## What the agent has

| Course topic (LangChain Essentials) | Where it is |
|---|---|
| `create_agent` | `shopmind/agent.py` → `build_agent()` |
| Tools | `shopmind/tools.py`: `search_store_docs`, `query_database`, `get_my_orders`, `cancel_order` |
| MCP | `shopmind/mcp_server.py` serves `check_stock`; the agent connects with `langchain-mcp-adapters` |
| Memory | `InMemorySaver` checkpointer, one conversation per `thread_id` |
| Streaming | `run_turn()` yields every tool call, tool result and the answer as they happen |
| Structured output | `SupportReply` (answer, sources, route) through `ToolStrategy` |
| Dynamic prompt | `role_prompt()`: different rules for customers and staff |
| Human-in-the-loop | `HumanInTheLoopMiddleware` pauses before `cancel_order` |
| Runtime context | `UserContext` (role, name, customer id), read by tools and the prompt |

## Demo results (5 scenes, all passed)

1. **Policy question → documents.** Answered "14 days" with a `[POL-001]` citation.
2. **Top customers, asked by staff → SQL.** The agent wrote a correct JOIN + GROUP BY query and listed the top 5.
3. **Same question, asked by a customer → refused.** See finding 1.
4. **"Phone under 15,000 that is in stock" (Arabic) → documents + filter + MCP.** It searched with
   `product_category=phones, max_price_egp=15000`, then called `check_stock` on the result, and
   recommended the Redmi Note 15 Pro (13,999 EGP, 18 in stock). The follow-up "وضمانه قد ايه؟"
   ("how long is its warranty?") was understood from memory: 12 months.
5. **Cancel order 1049 → paused for approval.** The order stayed `pending` while the agent was paused
   and became `cancelled` only after approval.

## What we learned

1. **The prompt alone did not stop the model; the code check did.** The customer prompt says "you cannot
   run SQL for customers". In scene 3 the model called `query_database` anyway. The tool checks the
   role in code and refused, so no data leaked. Rules that matter must live in code.

2. **The agent replaces the query rewriter.** In Phase 2 a separate Gemini call rewrote the question.
   Here the agent writes the search query and filters itself when it calls `search_store_docs`, so the
   search tool runs plain hybrid search and one request is saved per question.

3. **Filters as tool arguments work when the customer states them.** "تحت 15 الف" became
   `max_price_egp=15000`. Before the `product_category` argument existed, a search for a phone with a
   good camera returned a security camera first.

4. **Free-tier limits shaped the design.** Each Gemini model allows about 20 requests per day,
   `gemini-3.5-flash` and `gemini-3.6-flash` share one quota, and 3.7/3.8 often hang. The agent uses
   `ModelFallbackMiddleware` to move to `gemini-3.1-flash-lite` and then `gemini-3.5-flash-lite`.
   The demo saves finished scenes so it can continue the next day.

5. **Lite models still break the language rule.** Scene 2 was answered by a lite model: the facts were
   right but it replied in Arabic to an English question (same finding as Phase 3).

6. **Speed varies a lot.** Scenes took 3 to 34 seconds. The slow ones were waiting on a model that
   failed before the fallback answered.

## Limits

- Memory is in RAM (`InMemorySaver`): conversations are lost when the program stops. A database
  checkpointer (for example SQLite) would keep them.
- One demo run per scene is not an evaluation. Phase 5 measures the agent on a golden set, including
  whether it picks the right tool.
- `cancel_order` really changes `data/shop.db`. Run `python scripts/seed_db.py` to reset it.
- The SQL tool is read-only and SELECT-only, but staff can still read every table. Prompt injection
  and data-access tests are part of Phase 5.
