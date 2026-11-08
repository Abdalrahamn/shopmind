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
- [x] **Phase 1: Data and indexing** (40 documents, SQLite store, chunking, embeddings in Weaviate)
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
python scripts/seed_db.py   # builds data/shop.db
python scripts/ingest.py    # chunks, embeds and stores the documents in Weaviate
python scripts/check_index.py
streamlit run app.py        # local explorer at http://localhost:8501
```

## Data

**Store documents** (`data/docs/`, Markdown with YAML metadata) for a fictional Egyptian electronics store:

| Type | Count | Examples |
|---|---|---|
| Policies | 10 | returns, shipping, warranty, payment, instalments, cancellation, loyalty |
| FAQ | 10 | tracking, address changes, branches, trade-in |
| Products | 20 | phones, laptops, audio, accessories, smart home, gaming |

Each document has metadata used for filtering: `doc_type`, `category`, `status` (one policy is an **archived** 2024 version, to test date and status filters), `updated_at`, and for products `brand`, `price_egp`, `warranty_months`, `clearance`.

**SQL database** (`data/shop.db`, built by `scripts/seed_db.py`): 200 customers, 20 products with stock levels, 400 orders and their items. Products share SKUs and prices with the product documents, and shipping fees and loyalty tiers follow the written policies.

**Indexing:** documents are split by Markdown section, then to at most 800 characters with 120 overlap (88 chunks). Chunks are embedded with `all-MiniLM-L6-v2` (384 dimensions) and stored in the Weaviate collection `StoreDocs`.
