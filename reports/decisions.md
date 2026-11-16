# Decisions log

Why each important choice was made, what else was tried, and the number behind it.
Numbers come from [evaluation_report.md](evaluation_report.md).

## Data and indexing

**1. Chunking: split by Markdown headings first, then 800 characters with 120 overlap.**
- Why headings first: our documents are written in sections ("Return window", "Exchanges"). A section is one
  idea, so a chunk that follows the headings is one idea too, and its heading path goes into the chunk as context.
- Why 800 characters: the embedding model reads at most 256 word pieces (about 180 words). 800 characters is
  about 130 to 150 words, so the whole chunk is read and nothing is cut off silently.
- Why 120 overlap: a sentence that falls on a boundary is still whole in one of the two chunks.
- Result: 40 documents became 88 chunks.
- Not done: we did not measure other sizes. This choice follows from the model's limit, not from an experiment.

**2. Embedding model: `all-MiniLM-L6-v2` (384 dimensions), run locally.**
- Why: free, small, fast on a CPU, no API key.
- Cost of the choice: it is English-only. It found the right document for 1 of 4 Arabic questions. We kept it
  and fixed the problem with query rewriting (decision 5). A multilingual model would be the next thing to try.

**3. Vector database: Weaviate in Docker.**
- Why: it does keyword search (BM25), vector search, hybrid search and metadata filters in one place, and it is
  the database used in the RAG course.

**4. Metadata on every chunk** (`doc_type`, `category`, `price_egp`, `status`, `clearance`, …).
- Why: it allows hard filters ("under 15,000 EGP"), hides archived documents by default (the 2024 return policy
  said 14 business days for refunds; the current one says 5 to 10), and later let a tool state "this product is clearance".

## Retrieval

**5. Search method: hybrid (BM25 + semantic, merged with Reciprocal Rank Fusion).**
- Tried: BM25 alone (Recall@3 0.77), semantic alone (0.86), hybrid (0.89).
- Why: the two fail on different questions. BM25 finds exact codes like `SM-LT-003`; semantic finds
  "insurance if I drop my phone" when the policy says "accidental damage". Hybrid was never worse than the better one.
- Cost: 46 ms instead of 5 ms, which is nothing next to a model call.

**6. Query rewriting before search (fixed pipeline), and for Arabic queries (agent).**
- Why: Recall@3 went from 0.89 to 1.00, mostly by turning Arabic questions into English queries.
- In the agent the model writes the query itself, so the rewriter only runs when the query is in Arabic.

**7. Only filters the customer states are applied.**
- Tried: applying every filter the LLM extracted. Recall@3 fell to 0.77 ("where is my package" was filtered to
  policies; the answer is an FAQ).
- Now: a price limit or "the old policy" become filters; type, category and brand are hints only.

**8. No reranker.**
- Tried: a cross-encoder (`ms-marco-MiniLM-L6-v2`). Recall@3 fell from 0.89 to 0.82 and each query took about 1 second more.
- Why it did not help: 88 chunks is small, hybrid already puts the right chunk near the top, and the reranker is
  English web-search trained. It stays available (`rerank=True`) to test again on a bigger document set.

**9. BM25 stopword list.** Weaviate's default list does not include "how", "can", "I", "do", so FAQ titles
"How do I …" matched everything. Adding our list raised BM25 MRR from 0.68 to 0.77.

## Generation

**10. Answers only from retrieved text, with `[doc_id]` citations and a clear "I don't know".**
- Why: a support assistant that invents a policy is worse than one that says it does not know.
- Result: 0 made-up citations; all unanswerable questions were refused in every run.
- A check in code removes any citation that was not in the retrieved sources (it never fired, which is the wanted result).

**11. Temperature 0.** The same question at temperature 0 and 1.5 gave different wording but the same facts, so
temperature only adds variation we do not need.

## Agent

**12. One agent with tools, not a fixed pipeline.** The four demo questions need four different routes
(documents, SQL, documents + stock, an action). The agent chooses the tool per question: 25/25 right tool on the golden set.

**13. Stock comes from an MCP server, not from the documents.** A product page is written once; stock changes
every hour. `check_stock` reads the live database through MCP, and the prompt forbids guessing stock from a page.

**14. Safety rules live in code.** The model called the SQL tool for a customer in the Phase 4 demo and again
under prompt injection in Phase 5. The role check, the read-only connection, the ownership check and the human
approval before `cancel_order` are all code, so those calls did nothing. 14/14 direct attacks refused.

**15. Reply language is decided in code.** Asking the model to "reply in the user's language" gave 6/24.
Detecting Arabic letters in code and stating the language gave 25/25.

**16. At most 3 searches per turn.** One unanswerable question used 10 searches and 35,334 input tokens. The cap
is the main cost control, because every extra call re-sends the whole conversation.

**17. Structured final answer (`SupportReply`: answer, sources, route).** The app shows each part separately and
the evaluation can read the route and sources without parsing text.

## Model

**18. Main model: `deepseek/deepseek-v4.1-flash` through OpenRouter** (was Gemini's free tier in Phases 0 to 5).
- Why we moved: the free Gemini tier allows about 20 requests per model per day, so one evaluation run could not
  finish in a day and the agent fell back to weaker lite models.
- Why this model: it is DeepSeek's newest small model, supports tools and structured output, and is cheap
  (0.14 / 0.42 USD per million input / output tokens on OpenRouter).
- Result on the golden set: 25/25 correct, median 3.5 s, about 0.017 USD for all 25 questions (from token counts).
- Not measured: DeepSeek's larger "pro" models, and DeepSeek on the Phase 2 and 3 tests.

**19. One place creates models (`shopmind/llm.py`), chosen by `LLM_PROVIDER`.** Switching provider is one line in
`.env`; nothing else in the code knows which provider is used.

**20. Model fallback with a cooldown.** A model that fails is skipped for 5 minutes instead of being tried on
every call. On the free tier this cut the median turn from 28.4 s to 5.2 s.

## Evaluation

**21. A fixed golden set, re-run after every change.** The full re-run found a new failure (Arabic search query)
that the partial re-run of 7 questions had missed.

**22. String checks and an LLM judge together.** String checks are exact for numbers and free; the judge reads
meaning. Each caught mistakes of the other.

**23. Tracing on from day one (LangSmith).** The search loop and the dropped product name were both found by
reading traces, not by guessing.
