# Phase 3 findings and decisions

Numbers and every answer are in [generation_eval.md](generation_eval.md)
(run `python scripts/eval_generation.py` to reproduce; answers are cached).

## Results

| | gemini-3.5-flash | gemini-3.5-flash-lite |
|---|---|---|
| Facts correct | 10/10 | 9/10 |
| Says "I don't know" when it should | 3/3 | 3/3 |
| Cites only relevant documents | 7/7 | 7/7 |
| Made-up citations | 0 | 0 |
| Replies in the customer's language | 10/10 | 5/10 |
| Average latency | 4.2 s | 1.0 s |
| Average output tokens | 739 | 95 |

## What we learned

1. **Grounding rules stopped hallucination on this test.** Neither model invented an
   answer for the three questions the documents cannot answer. The hardest one was
   "price of the iPhone 17 Pro Max": the catalogue has the iPhone 17 at 57,999 EGP, and
   both models refused instead of quoting that price.

2. **Retrieval filters protect generation.** For "how long do card refunds take?", both
   models answered 5 to 10 business days. The archived 2024 policy (14 business days) never
   reached the prompt, because Phase 2 hides archived documents.

3. **The lite model ignores the language rule.** It replied in Arabic to 5 of 8 English
   questions. Its one "wrong fact" is the same problem: the fact was correct but written
   in Arabic. It also expanded "QNB" into a wrong Arabic bank name, a small detail that
   was not in the sources.

4. **Speed and cost against quality.** The lite model is about 4 times faster and writes
   about 8 times fewer output tokens (the main model also spends tokens on thinking).
   For customer-facing answers the language mistakes are not acceptable, so the main
   model stays the answer model and the lite model keeps the small job of query rewriting.

5. **Temperature 0 is not fully deterministic.** The same question gave three different
   wordings in three runs at temperature 0, and three at temperature 1.5. The facts and
   citations were correct in all six. So temperature changed the wording, not the content,
   because the content is fixed by the sources. We keep temperature 0.

6. **The citation check never fired**, which is the result we want: no model cited a
   document that was not retrieved. The check stays in the code as a guardrail.

## Decisions

- Answer model: `gemini-3.5-flash`, temperature 0, 6 chunks of context.
- Rewrite model: `gemini-3.5-flash-lite` (unchanged from Phase 2).
- Answers always carry `[doc_id]` citations; citations not found in the retrieved sources
  are removed in code.

## Limits of this evaluation

- 10 questions is a small test. The checks are simple string matches (for example the
  answer must contain "14"), which can miss a wrong answer that happens to contain the
  right number. Phase 5 adds an LLM judge and a larger golden set.
- The temperature test used one question and three runs per setting.
- The free tier (about 20 requests per model per day) limits how much we can test in one day.
