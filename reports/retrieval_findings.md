# Phase 2 findings and decisions

The numbers come from [retrieval_eval.md](retrieval_eval.md) (28 labeled questions, K = 3,
run `python scripts/eval_retrieval.py` to reproduce).

## Results in one line each

| Setup | Recall@3 | MRR | Note |
|---|---|---|---|
| TF-IDF / BM25 from scratch | 0.75 | 0.70–0.74 | Good on exact words, blind to paraphrases and Arabic |
| BM25 (Weaviate) | 0.77 | 0.77 | Same idea; was 0.71 / 0.68 before the stopword fix |
| Semantic | 0.86 | 0.80 | Understands paraphrases, misses exact codes like `SM-LT-003` |
| Hybrid RRF | 0.89 | 0.87 | Best of both; same as Weaviate's built-in hybrid |
| Hybrid RRF + rerank | 0.82 | 0.79 | Worse, and ~20x slower |
| **Rewrite + Hybrid RRF** | **1.00** | **0.98** | **Chosen default** |

Precision@3 looks low (0.42 at best) because most questions have only one relevant
document, so even a perfect search scores 1/3 on them. Recall@3 and MRR are the useful numbers here.

## What we learned

1. **Keyword and semantic search fail on different questions.** BM25 nailed `SM-LT-003`
   and "Vodafone Cash" but missed "insurance if I drop my phone" (the policy says
   "accidental damage"). Semantic search did the opposite. Hybrid with Reciprocal Rank
   Fusion kept the strengths of both: it never did worse than the better of the two.

2. **Stopwords matter for BM25.** Weaviate's default English stopword list does not
   include "how", "can", "I", "do". For "can I buy with valU?", BM25 ranked FAQs titled
   "How do I ..." above the instalments policy. Adding our stopword list to the
   collection (`scripts/ingest.py`) raised BM25 MRR from 0.68 to 0.77.

3. **Our embedding model only speaks English.** `all-MiniLM-L6-v2` found the right
   document for 1 of 4 Arabic questions. Rewriting the question into English with Gemini
   fixed all four.

4. **Letting the LLM pick filters hurt.** The first version applied every filter Gemini
   extracted. Recall dropped to 0.77: "where is my package" was filtered to policies
   (the answer is an FAQ), and "can I return AirPods" became `policy + brand Apple`,
   which matches nothing because policies have no brand. Now only constraints the customer
   actually states become filters (a price limit, or asking about an old policy); type,
   category and brand stay as hints.

5. **The reranker made things worse here.** `ms-marco-MiniLM-L6-v2` is trained on English
   web search. It dropped the exact-code question and all Arabic ones, and costs about
   1 second per query on CPU. With only 88 chunks, hybrid search already puts the right
   chunk near the top, so there is little left for a reranker to fix. It stays available
   as an option (`rerank=True`) to re-test when the document set grows.

6. **Archived documents need a default filter.** Without `status = active`, the 2024 return
   policy showed up for return questions. It is now hidden unless the customer asks about
   an old policy.

## Decisions

- Default retrieval for the agent: **rewrite with Gemini, then Hybrid RRF**, archived hidden,
  no reranker (`shopmind.retrieval.DEFAULT_SEARCH`).
- Query rewriting uses `gemini-3.5-flash-lite` with fallbacks to other Gemini models, and
  every rewrite is cached on disk, because the free tier allows about 20 requests per model per day.

## Limits of this evaluation

- 28 questions is small, and the same person wrote the documents and the questions, so the
  questions may be easier than real customer messages. Phase 5 builds a larger golden set.
- The filter rule in point 4 was chosen after looking at these results, so the 1.00 is
  optimistic. It needs to be confirmed on new questions.
