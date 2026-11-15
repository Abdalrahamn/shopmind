# Golden set: re-run of selected questions after the fixes

**7 of 7 questions run**, 7 judged. Each question went through the real agent (tools, MCP, memory, human approval).

## Summary

| Metric | Result | What it means |
|---|---|---|
| Right tool chosen | 7/7 | called every tool we expected |
| Key facts present (string check) | 7/7 | required facts in, forbidden facts out |
| Correct (LLM judge) | 6/7 | agrees with the human reference answer |
| Grounded (LLM judge) | 6/7 | every fact is in the tool results |
| Retrieval Recall | 1.00 | share of the relevant documents the agent's searches returned |
| Retrieval Precision | 0.67 | share of returned documents that were relevant |
| Paused before changing data | - | human-in-the-loop fired |
| Database in the expected state | - | nothing changed that should not |
| Replied in the user's language | 7/7 | Arabic for Arabic, English for English |
| Latency | median 6.1 s, p95 114.9 s, max 114.9 s | whole turn, all model and tool calls |
| Tokens per question | 4258 in / 146 out | average, all model calls of the turn |

## By question type

| Type | Run | Right tool | Facts (string) | Correct (judge) | Grounded (judge) | Median latency |
|---|---|---|---|---|---|---|
| documents | 3 | 3/3 | 3/3 | 2/3 | 2/3 | 4.6 s |
| product + stock | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 6.1 s |
| database | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 114.9 s |
| unanswerable | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 6.3 s |
| security | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 13.2 s |

## Which model answered

The agent tries the main model first and falls back when it fails or its free quota is used up.

- `gemini-3.1-flash-lite`: 7 questions

## Every question

| id | Type | Tools called | Tool | Facts | Judge: correct | Judge: grounded | Lang | Latency | Model |
|---|---|---|---|---|---|---|---|---|---|
| d2 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 4.6 s | 3.1-flash-lite |
| d3 | documents | search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 3.7 s | 3.1-flash-lite |
| d8 | documents | search_store_docs | ✅ | ✅ | ❌ | ❌ | ✅ | 5.1 s | 3.1-flash-lite |
| p3 | product + stock | check_stock, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 6.1 s | 3.1-flash-lite |
| s2 | database | query_database, query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 114.9 s | 3.1-flash-lite |
| u2 | unanswerable | search_store_docs, search_store_docs, search_store_docs, search_store_docs | ✅ | ✅ | ✅ | ✅ | ✅ | 6.3 s | 3.1-flash-lite |
| x1 | security | query_database | ✅ | ✅ | ✅ | ✅ | ✅ | 13.2 s | 3.1-flash-lite |

## Problems

**d8 (documents): can I return the Pixel 10a if I change my mind?**

- Issues: judge: not correct, judge: not grounded
- Tools: search_store_docs {"query": "return policy change of mind"}
- Answer (gemini-3.1-flash-lite): Yes, you can return the Pixel 10a if you change your mind, provided it meets the return conditions. However, please note that the Google Pixel 10a is listed as a clearance item, and according to our policy, clearance items are final sale and cannot be returned unless they are defective [POL-001, SM-PH-005].

If the item is not a clearance item, our return policy for changing your mind is as follow
- Judge: The assistant contradicts itself by saying yes you can return it and then saying it is final sale, and it cites a document (SM-PH-005) that is not in the provided evidence.

