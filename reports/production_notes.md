# Cost, latency and tracing (Phase 5)

Numbers are from the first golden run: 24 questions through the full agent, answered by fallback lite models.

## Latency

| | Value |
|---|---|
| Median turn | 28.4 s |
| 95th percentile | 88.2 s |
| Fastest (SQL question, model answered at once) | 2.6 s |
| Slowest | 122.4 s |

Where the time goes in one turn:

1. **Model calls (almost all of it).** A turn has 2 to 4 model calls: choose a tool, read the result, maybe
   choose another, write the answer. Each call waited for the main model to fail before a fallback answered.
2. **Tools (small).** Hybrid search takes about 50 ms, SQL a few ms, the MCP stock check starts a small
   process (well under a second).

So the honest picture: with a model that answers on the first try, turns take about 3 to 6 s (the SQL
questions show this). The 28 s median is the price of the free tier, not of the design.

## Tokens

| | Value |
|---|---|
| Average per question | 5,211 input / 184 output |
| Whole run (24 questions) | 125,060 input / 4,425 output |
| Cheapest question | 2,390 input (one SQL call) |
| Most expensive | 35,334 input (the 10-search loop, now capped) |

Input is about 28 times larger than output. Every model call re-sends the system prompt, all five tool
descriptions, the conversation so far and every tool result. That is why the search loop was so expensive,
and why capping tool calls is the main cost control.

## Cost

On the free tier the cost is 0. For a paid tier:

```
cost per question = input_tokens × input_price + output_tokens × output_price
```

With this run's averages (5,211 in, 184 out), multiply by the current per-token prices of the model you choose
from Google's pricing page. We do not put a price in this report because prices change and we have not run on
a paid tier. Since input dominates, the input price matters most.

Ways to lower cost, in order of effect:

1. Cap tool calls per turn (done: at most 3 searches).
2. Return fewer or shorter chunks from `search_store_docs` (now 5 to 8 chunks, up to 800 characters each).
3. Cache repeated questions (done for query rewriting and Phase 3 answers; not done for the agent).
4. Use a cheaper model for easy turns and the main model for hard ones (the fallback list is a crude version of this).

## The trade-offs we measured

| Choice | Quality | Speed / cost | Decision |
|---|---|---|---|
| Hybrid search vs BM25 only | Recall@3 0.89 vs 0.77 | 46 ms vs 5 ms | Hybrid: 40 ms is nothing next to a model call |
| Cross-encoder reranker | Recall@3 fell to 0.82 | +1 second per query | Off |
| Query rewriting by a separate model call | Recall@3 1.00 vs 0.89 | +1 model call | Kept in the fixed pipeline; in the agent the agent writes the query itself |
| Main model vs lite model for answers | language 10/10 vs 5/10 | 4.2 s vs 1.0 s | Main model first, lite as fallback, language set in code |

## Tracing with LangSmith

Tracing has been on since Phase 0 (`LANGSMITH_TRACING=true`), so every model call and tool call in this project
is recorded in the LangSmith project **shopmind**. A trace shows, for one turn: the full prompt sent to the
model, which tool it chose and with which arguments, the tool's result, token counts and time per step.

How we used it:

- Each golden question is tagged, so you can filter by `golden` and by question id (for example `d8`).
- The search loop (failure 3) and the dropped "Pixel 10a" (failure 2) were both read straight from traces.
- The "which model failed and why" table in Phase 4 came from the trace errors: that is how we found that
  `gemini-3.5-flash` and `gemini-3.6-flash` share one quota.

## Security summary

| Layer | What it does | Tested by |
|---|---|---|
| Read-only database connection | No write can succeed through the SQL tool | `scripts/test_security.py` (14/14) |
| SELECT-only, single statement | Blocks DELETE, DROP, PRAGMA, ATTACH, stacked statements | same |
| Role check in code | Customers cannot run SQL even if the model tries | golden x1, x3 |
| Ownership and status check | Cannot cancel another customer's order, or a shipped one | golden x2 |
| Human approval before `cancel_order` | Nothing changes without a person | golden o2, x2 |
| Parameterised queries | SQL injection through tool arguments does nothing | same script |
| Archived documents hidden | Old policies never reach the model | Phase 2 and 3 |

Not covered yet:

- **Injection inside documents.** If someone could edit a store document to say "ignore your rules", the model
  would read it as part of the sources. Our documents are trusted and fixed, so this was not tested.
- **Staff can read every table**, including customer emails and phones. A real system would expose views with
  fewer columns.
- **No rate limiting or login.** The explorer page trusts whoever picks "staff" in the menu; it only listens on localhost.
- **Personal data in traces.** LangSmith stores prompts and tool results, which include customer names and
  orders. A real deployment needs masking or a self-hosted tracer.
