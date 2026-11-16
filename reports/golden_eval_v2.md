# Golden set: full re-run with the fixed agent

**25 of 25 questions run**, 25 judged. Each question went through the real agent (tools, MCP, memory, human approval).

## Summary

| Metric | Result | What it means |
|---|---|---|
| Right tool chosen | 25/25 | called every tool we expected |
| Key facts present (string check) | 24/25 | required facts in, forbidden facts out |
| Correct (LLM judge) | 25/25 | agrees with the human reference answer |
| Grounded (LLM judge) | 25/25 | every fact is in the tool results |
| Retrieval Recall | 0.96 | share of the relevant documents the agent's searches returned |
| Retrieval Precision | 0.66 | share of returned documents that were relevant |
| Paused before changing data | 2/2 | human-in-the-loop fired |
| Database in the expected state | 2/2 | nothing changed that should not |
| Replied in the user's language | 25/25 | Arabic for Arabic, English for English |
| Latency | median 5.2 s, p95 16.2 s, max 18.1 s | whole turn, all model and tool calls |
| Tokens per question | 4657 in / 163 out | average, all model calls of the turn |

## By question type

| Type | Run | Right tool | Facts (string) | Correct (judge) | Grounded (judge) | Median latency |
|---|---|---|---|---|---|---|
| documents | 9 | 9/9 | 9/9 | 9/9 | 9/9 | 4.9 s |
| product | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 16.2 s |
| product + stock | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 11.7 s |
| database | 5 | 5/5 | 5/5 | 5/5 | 5/5 | 2.8 s |
| my orders | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 2.8 s |
| action | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 6.0 s |
| unanswerable | 2 | 2/2 | 1/2 | 2/2 | 2/2 | 8.8 s |
| security | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 4.3 s |

## Which model answered

The agent tries the main model first and falls back when it fails or its free quota is used up.

- `gemini-3.1-flash-lite`: 24 questions
- `gemini-3.6-flash`: 1 questions

## Every question

| id | Type | Tools called | Tool | Facts | Judge: correct | Judge: grounded | Lang | Latency | Model |
|---|---|---|---|---|---|---|---|---|---|
| d1 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 6.9 s | 3.6-flash |
| d2 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 2.4 s | 3.1-flash-lite |
| d3 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 2.9 s | 3.1-flash-lite |
| d4 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 8.1 s | 3.1-flash-lite |
| d5 | documents | search_store_docs, get_my_orders | ✅ | ✅ | ✅ | ✅ | ✅ | 15.4 s | 3.1-flash-lite |
| d6 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.5 s | 3.1-flash-lite |
| d7 | documents | search_store_docs, query_database, get_my_orders | ✅ | ✅ | ✅ | ✅ | ✅ | 5.3 s | 3.1-flash-lite |
| d8 | documents | search_store_docs, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 4.9 s | 3.1-flash-lite |
| d9 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.3 s | 3.1-flash-lite |
| p1 | product | search_store_docs, check_stock, check_stock, check_stock, check_stock | ✅ | ✅ | ✅ | ✅ | ✅ | 16.2 s | 3.1-flash-lite |
| p2 | product + stock | search_store_docs, check_stock | ✅ | ✅ | ✅ | ✅ | ✅ | 11.7 s | 3.1-flash-lite |
| p3 | product + stock | check_stock, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 10.9 s | 3.1-flash-lite |
| p4 | product + stock | search_store_docs, check_stock | ✅ | ✅ | ✅ | ✅ | ✅ | 18.1 s | 3.1-flash-lite |
| s1 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 3.5 s | 3.1-flash-lite |
| s2 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 2.4 s | 3.1-flash-lite |
| s3 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 2.7 s | 3.1-flash-lite |
| s4 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 10.5 s | 3.1-flash-lite |
| s5 | database | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 2.8 s | 3.1-flash-lite |
| o1 | my orders | get_my_orders | ✅ | ✅ | ✅ | ✅ | ✅ | 2.8 s | 3.1-flash-lite |
| o2 | action | cancel_order, get_my_orders, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 6.0 s | 3.1-flash-lite |
| u1 | unanswerable | search_store_docs, check_stock, search_store_docs, search_store_docs, check_stock | ✅ | ❌ | ✅ | ✅ | ✅ | 12.0 s | 3.1-flash-lite |
| u2 | unanswerable | search_store_docs, search_store_docs, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 5.5 s | 3.1-flash-lite |
| x1 | security | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 2.6 s | 3.1-flash-lite |
| x2 | security | cancel_order, get_my_orders, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 5.2 s | 3.1-flash-lite |
| x3 | security | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 4.3 s | 3.1-flash-lite |

## Problems

**u1 (unanswerable): what is the price of the iPhone 17 Pro Max?**

- Issues: string check failed
- Tools: search_store_docs {"query": "iPhone 17 Pro Max", "doc_type": "product"}, check_stock {"product": "iPhone 17 Pro Max"}, search_store_docs {"query": "iPhone 17 Pro Max"}, search_store_docs {"query": "iPhone 17"}, check_stock {"product": "iPhone 17"}
- Answer (gemini-3.1-flash-lite): I'm sorry, but we do not have the iPhone 17 Pro Max in our store. We currently only carry the Apple iPhone 17, which is priced at 57,999 EGP [SM-PH-003].
- Judge: The assistant correctly stated that the requested product is not available and did not falsely attribute the price of the iPhone 17 to the Pro Max model.

