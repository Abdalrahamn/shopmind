# Retrieval evaluation (Phase 2)

28 labeled questions, document level, K = 3. Archived documents are filtered out by default.

| Setup | Questions | Precision@3 | Recall@3 | MRR | ms / query |
|---|---|---|---|---|---|
| TF-IDF (scratch) | 28 | 0.32 | 0.75 | 0.74 | 0 |
| BM25 (scratch) | 28 | 0.32 | 0.75 | 0.70 | 0 |
| BM25 (Weaviate) | 28 | 0.32 | 0.77 | 0.77 | 5 |
| Semantic | 28 | 0.36 | 0.86 | 0.80 | 33 |
| Hybrid RRF | 28 | 0.37 | 0.89 | 0.87 | 46 |
| Hybrid (Weaviate) | 28 | 0.37 | 0.89 | 0.87 | 89 |
| Hybrid RRF + rerank | 28 | 0.35 | 0.82 | 0.79 | 1197 |
| Rewrite + Hybrid RRF | 28 | 0.42 | 1.00 | 0.98 | 102 |
| Rewrite + Hybrid + rerank | 28 | 0.40 | 0.96 | 0.97 | 1467 |

## Recall@3 by question type

| Setup | arabic | direct | exact term | multi-doc | paraphrase | product |
|---|---|---|---|---|---|---|
| TF-IDF (scratch) | 0.00 | 1.00 | 0.67 | 1.00 | 0.78 | 1.00 |
| BM25 (scratch) | 0.00 | 1.00 | 0.67 | 1.00 | 0.78 | 1.00 |
| BM25 (Weaviate) | 0.00 | 1.00 | 1.00 | 1.00 | 0.72 | 1.00 |
| Semantic | 0.25 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 |
| Hybrid RRF | 0.25 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Hybrid (Weaviate) | 0.25 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Hybrid RRF + rerank | 0.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 |
| Rewrite + Hybrid RRF | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Rewrite + Hybrid + rerank | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 |

## Misses (no relevant document in the top 3)

- **TF-IDF (scratch)** (7): q09 (got POL-001, SM-GM-002, SM-PH-001), q14 (got POL-002), q19 (got nothing), q25 (got nothing), q26 (got nothing), q27 (got nothing), q28 (got nothing)
- **BM25 (scratch)** (7): q09 (got POL-001, SM-GM-002, SM-PH-001), q14 (got POL-002), q19 (got nothing), q25 (got nothing), q26 (got nothing), q27 (got nothing), q28 (got nothing)
- **BM25 (Weaviate)** (6): q09 (got SM-GM-002, SM-PH-001, SM-LT-002), q14 (got POL-002), q25 (got nothing), q26 (got nothing), q27 (got nothing), q28 (got nothing)
- **Semantic** (4): q19 (got SM-AU-001, SM-PH-001, SM-AU-004), q25 (got POL-002, FAQ-003, FAQ-004), q26 (got POL-002, FAQ-003, FAQ-004), q28 (got POL-002, FAQ-004, FAQ-003)
- **Hybrid RRF** (3): q25 (got POL-002, FAQ-003, FAQ-004), q26 (got POL-002, FAQ-003, FAQ-004), q28 (got POL-002, FAQ-004, FAQ-003)
- **Hybrid (Weaviate)** (3): q25 (got POL-002, FAQ-003, FAQ-004), q26 (got POL-002, FAQ-003, FAQ-004), q28 (got POL-002, FAQ-004, FAQ-003)
- **Hybrid RRF + rerank** (5): q19 (got SM-AU-001, SM-LT-004, SM-PH-001), q25 (got FAQ-004, POL-007, POL-002), q26 (got POL-007, FAQ-004, SM-PH-005), q27 (got POL-007, FAQ-004, SM-PH-005), q28 (got FAQ-004, POL-007, SM-PH-005)
- **Rewrite + Hybrid + rerank** (1): q19 (got SM-AU-001, SM-LT-004, SM-PH-001)
