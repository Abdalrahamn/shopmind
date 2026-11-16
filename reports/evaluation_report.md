# ShopMind evaluation report

One page with the numbers from every phase. Each table links to the full report it came from.
All test sets are small and written by the project's author, so read the numbers as "works on these
questions", not as a guarantee on real customer traffic (see Limits at the end).

## 1. Retrieval: which search method? (Phase 2)

28 labelled questions, top 3 results. Full table: [retrieval_eval.md](retrieval_eval.md), discussion: [retrieval_findings.md](retrieval_findings.md).

| Method | Recall@3 | MRR | Note |
|---|---|---|---|
| TF-IDF / BM25 written from scratch | 0.75 | 0.70 to 0.74 | Good on exact words, blind to paraphrases and Arabic |
| BM25 (Weaviate) | 0.77 | 0.77 | Was 0.71 / 0.68 before the stopword fix |
| Semantic (embeddings) | 0.86 | 0.80 | Understands paraphrases, misses exact codes like `SM-LT-003` |
| Hybrid (BM25 + semantic, RRF) | 0.89 | 0.87 | Best of both |
| Hybrid + cross-encoder reranker | 0.82 | 0.79 | Worse, and about 1 second slower per query |
| **Query rewriting + Hybrid** | **1.00** | **0.98** | **Chosen** |

- **Recall@3**: of the documents that hold the answer, the share found in the top 3.
- **MRR**: how high the first correct document is (1.0 = always first).

## 2. Generation: are answers grounded? (Phase 3)

10 questions through the fixed RAG pipeline (search, then answer). Full report: [generation_eval.md](generation_eval.md).

| | gemini-3.5-flash | gemini-3.5-flash-lite |
|---|---|---|
| Facts correct | 10/10 | 9/10 |
| Says "I don't know" when it should | 3/3 | 3/3 |
| Cites only relevant documents | 7/7 | 7/7 |
| Made-up citations | 0 | 0 |
| Replies in the customer's language | 10/10 | 5/10 |
| Average latency | 4.2 s | 1.0 s |

## 3. The whole agent on the golden set (Phase 5)

25 questions through the real agent: 9 documents, 4 product and stock, 5 SQL, 2 orders, 2 unanswerable, 3 security.
Three runs: before the fixes, after the fixes on the same Gemini lite models, and after switching to DeepSeek.

| Metric | Gemini lite, first run (24 q) | Gemini lite, after fixes (25 q) | DeepSeek v4.1 flash (25 q) |
|---|---|---|---|
| Right tool chosen | 24/24 | 25/25 | 25/25 |
| Correct (LLM judge) | 23/24 | 25/25 | 25/25 |
| Grounded (LLM judge) | 23/24 | 25/25 | 21/25 * |
| Retrieval Recall / Precision | 0.95 / 0.63 | 0.96 / 0.66 | 0.96 / 0.70 |
| Paused before changing data | 2/2 | 2/2 | 1/1 ** |
| Database in the expected state | 2/2 | 2/2 | 2/2 |
| Replied in the user's language | 6/24 | 25/25 | 25/25 |
| Latency: median / max | 28.4 s / 122.4 s | 5.2 s / 18.1 s | 3.5 s / 7.0 s |
| Tokens per question (in / out) | 5,211 / 184 | 4,657 / 163 | 3,919 / 305 |

Full reports: [first run](golden_eval.md), [after fixes](golden_eval_v2.md), [DeepSeek](golden_eval_deepseek.md).

\* The judge in the third run is DeepSeek too and is stricter. The four "not grounded" answers are small
inferences (for example "confirmed, so it has not shipped yet"), not wrong facts; all four were judged correct.

\** In the DeepSeek run the agent checked the customer's orders first and refused to cancel someone else's
order without calling `cancel_order`, so only one question reached the approval step. Both paths are accepted.

**Cost of the DeepSeek run:** 97,969 input and 7,631 output tokens for the 25 questions, about 0.017 USD at
OpenRouter's listed prices (0.14 / 0.42 USD per million tokens). Calculated from token counts, not from an invoice.

## 4. Security

| Test | Result | Report |
|---|---|---|
| 14 direct attacks on the tools (DELETE, DROP, hidden writes, other customers' orders, SQL injection) | 14/14 refused, database unchanged | [security_tests.md](security_tests.md) |
| 3 attack questions in the golden set (prompt injection, another customer's order, personal data) | 3/3 no leak, in all three runs | golden reports above |
| Prompt injection hidden inside a retrieved document | 2/2 ignored (Gemini lite only) | [security_doc_injection.md](security_doc_injection.md) |

## 5. The four acceptance questions (Phase 6)

Run on the final agent with DeepSeek. Full transcript: [agent_demo.md](agent_demo.md).

| Demo question | Route | Result | Time |
|---|---|---|---|
| "What is the return policy?" | RAG | Answered from `[POL-001]` with citations | 4.3 s |
| "Who are the top 3 customers by spend?" (staff) | SQL | Ali Mahfouz, Yasmin Sherif, Hassan Sherif with totals | 3.5 s |
| "عايز موبايل تحت 15 الف ويكون متوفر دلوقتي" | RAG + price filter + MCP | Redmi Note 15 Pro, 13,999 EGP, 18 in stock | 4.5 s |
| "Cancel order #1049." | Human-in-the-loop | Paused; order stayed `pending` until a human approved, then `cancelled` | 1.8 s |

The original task wrote "a winter jacket under 1,000 EGP" and "order #5". Our store sells electronics and
order ids start at 1001, so the same skills are shown with a phone under 15,000 EGP and order 1049.

## 6. Failure cases

Eight failures found by the golden set, each with cause and fix. Details: [failure_cases.md](failure_cases.md).

| # | Failure | Cause | Fix | Status |
|---|---|---|---|---|
| 1 | Arabic replies to English questions (18 of 24) | The prompt asked the model to detect the language | Language detected in code and stated in the prompt | Fixed: 25/25 |
| 2 | "Yes, you can return the Pixel 10a" (it is clearance) | Query dropped the product name; then the model did not connect two documents | Search also uses the customer's words; the tool writes a clearance note next to the product | Fixed |
| 3 | 10 searches for one unanswerable question | Nothing told the agent to stop | At most 3 searches per turn (`ToolCallLimitMiddleware`) | Fixed: 35,334 → 9,876 input tokens |
| 4 | The model obeyed a prompt injection and called the SQL tool | A prompt rule is only a request | None needed: the tool checks the role in code and refused | Held |
| 5 | String check failed a correct answer | String checks cannot read meaning | Keep both string checks and an LLM judge | By design |
| 6 | Median turn 28 s, worst 122 s | Every call waited for the main model to fail | `FallbackWithCooldown` skips a failed model for 5 minutes | Fixed: 5.2 s |
| 7 | A question could not run (all models busy) | Free-tier limits | The evaluation saves progress and continues | Fixed |
| 8 | Arabic search query, then an invented answer | Embeddings are English-only | Arabic queries are rewritten to English before searching | Fixed |

The lesson that repeats in 1, 2, 4 and 8: **what must always hold goes in code, not in the prompt.**

## Limits

- **Small test sets** (28, 10 and 25 questions), written by the same person who wrote the documents.
- **The judge is an LLM** and made mistakes we caught by hand; its marks need human spot checks.
- **Phases 2 and 3 were measured on Gemini only.** After the switch to DeepSeek only the golden set and the demo were re-run.
- **The document-injection test is light**: one poisoned text, two questions, one model, and no code-level defence.
- **Not covered**: load (many users at once), long conversations, and personal data stored in traces.
