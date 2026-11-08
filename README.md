# ShopMind

An AI assistant for an e-commerce store. It answers questions from two sources and decides which one each question needs:

- **Store documents** (FAQ, policies, product descriptions) through a RAG pipeline
- **SQL database** (orders, customers, products, stock)

This is a capstone project that applies *LangChain Essentials (v1)* and *Retrieval Augmented Generation* (DeepLearning.AI). It uses only free tools.

## Stack

| Part | Tool |
|---|---|
| LLM | Gemini API (free tier) via `langchain-google-genai` |
| Agent framework | LangChain v1 / LangGraph |
| Vector database | Weaviate (Docker) |
| Embeddings | sentence-transformers |
| SQL database | SQLite |
| Tracing and evaluation | LangSmith |

## Roadmap

- [x] **Phase 0: Setup** (environment, keys, Weaviate, tracing)
- [ ] **Phase 1: Data and indexing**
- [ ] **Phase 2: Retrieval** (BM25, semantic, hybrid + RRF, filtering, query rewriting, reranking)
- [ ] **Phase 3: Generation** (citations, "I don't know", model comparison)
- [ ] **Phase 4: Agent** (tools, MCP, memory, streaming, structured output, human-in-the-loop)
- [ ] **Phase 5: Evaluation and production** (golden set, Precision@K / Recall@K, LLM-as-judge, cost, latency, security)
- [ ] **Phase 6: Deliverables** (architecture diagram, eval report, demo)

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
cp .env.example .env        # then add your GOOGLE_API_KEY and LANGSMITH_API_KEY
docker compose up -d        # starts Weaviate on localhost:8080
python check_setup.py       # all four checks should print [OK]
```
