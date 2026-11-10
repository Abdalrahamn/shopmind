"""ShopMind explorer: a local page to see what Phases 0 and 1 built.

Run: streamlit run app.py   (then open http://localhost:8501)
"""
import os
import sqlite3

import pandas as pd
import streamlit as st
from shopmind.config import DB_PATH, DOCS_DIR, EMBEDDING_MODEL, GEMINI_MODEL, ROOT
from shopmind.documents import chunk_documents, load_documents
from shopmind.retrieval import Retriever, SearchFilters

st.set_page_config(page_title="ShopMind Explorer", page_icon="🛒", layout="wide")


@st.cache_resource
def retriever():
    return Retriever()


@st.cache_data
def documents():
    return load_documents(DOCS_DIR)


def sql(query: str, params=()) -> pd.DataFrame:
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:  # read-only
        return pd.read_sql_query(query, con, params=params)


st.title("🛒 ShopMind Explorer")
st.caption("Phase 0 (setup), Phase 1 (data and indexing) and Phase 2 (retrieval).")

tab_setup, tab_docs, tab_chunks, tab_search, tab_eval, tab_sql = st.tabs(
    ["⚙️ Setup", "📄 Documents", "✂️ Chunks", "🔎 Search", "📊 Retrieval eval", "🗄️ SQL database"]
)

# ---------------------------------------------------------------- Setup
with tab_setup:
    st.subheader("Phase 0: are all the tools working?")
    cols = st.columns(4)

    if os.getenv("GOOGLE_API_KEY"):
        cols[0].success(f"**Gemini**\n\nkey found · `{GEMINI_MODEL}`")
    else:
        cols[0].error("**Gemini**\n\nGOOGLE_API_KEY missing")

    if os.getenv("LANGSMITH_API_KEY"):
        cols[1].success(f"**LangSmith**\n\nproject `{os.getenv('LANGSMITH_PROJECT')}`")
    else:
        cols[1].error("**LangSmith**\n\nLANGSMITH_API_KEY missing")

    try:
        total = retriever().collection.aggregate.over_all(total_count=True).total_count
        cols[2].success(f"**Weaviate**\n\nready · {total} chunks stored")
    except Exception as e:
        cols[2].error(f"**Weaviate**\n\n{type(e).__name__}")

    cols[3].success(f"**Embeddings**\n\n`{EMBEDDING_MODEL.split('/')[-1]}` · 384 dims")

    if st.button("Send a test message to Gemini"):
        from langchain.chat_models import init_chat_model
        with st.spinner("Asking Gemini..."):
            reply = init_chat_model(f"google_genai:{GEMINI_MODEL}").invoke("Say hello in Egyptian Arabic in one short sentence")
        st.info(reply.text)
        st.caption("This call is now visible in LangSmith → project shopmind.")

# ---------------------------------------------------------------- Documents
with tab_docs:
    docs = documents()
    st.subheader(f"Phase 1: {len(docs)} store documents")
    table = pd.DataFrame([{k: d.metadata.get(k) for k in
                           ("doc_id", "title", "doc_type", "category", "status", "updated_at", "price_egp")}
                          for d in docs])
    kind = st.segmented_control("Type", ["all", "policy", "faq", "product"], default="all")
    if kind and kind != "all":
        table = table[table.doc_type == kind]
    st.dataframe(table, hide_index=True, width="stretch")

    choice = st.selectbox("Open a document", [d.metadata["doc_id"] for d in docs])
    doc = next(d for d in docs if d.metadata["doc_id"] == choice)
    left, right = st.columns([1, 2])
    left.markdown("**Metadata**")
    left.json({k: v for k, v in doc.metadata.items()})
    right.markdown(doc.page_content)

# ---------------------------------------------------------------- Chunks
with tab_chunks:
    chunks = chunk_documents(documents())
    st.subheader(f"Chunking: {len(documents())} documents → {len(chunks)} chunks")
    st.caption("Split by Markdown section first, then to at most 800 characters with 120 characters of overlap.")
    choice = st.selectbox("Show the chunks of", [d.metadata["doc_id"] for d in documents()], key="chunk_doc")
    for c in [c for c in chunks if c.metadata["doc_id"] == choice]:
        with st.container(border=True):
            st.caption(f"chunk {c.metadata['chunk_index']} · {len(c.page_content)} characters")
            st.text(c.page_content)

# ---------------------------------------------------------------- Search (Phase 2)
METHOD_LABELS = {
    "hybrid": "Hybrid RRF (BM25 + semantic)",
    "semantic": "Semantic (meaning)",
    "bm25": "BM25 (Weaviate)",
    "bm25_scratch": "BM25 (from scratch)",
    "tfidf": "TF-IDF (from scratch)",
    "weaviate_hybrid": "Hybrid (Weaviate built-in)",
}


def show_hits(hits):
    if not hits:
        st.warning("No results.")
    for i, h in enumerate(hits, 1):
        p = h.properties
        badge = " 🗄️ ARCHIVED" if p["status"] == "archived" else ""
        ranks = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in h.extra.items() if k.endswith("rank") or k == "before_rerank")
        with st.expander(f"{i}. {p['doc_id']} · {p['title']}{badge} · score {h.score:.3f}", expanded=i <= 2):
            st.caption(f"{p['doc_type']} · {p['category']} · section: {p['section']}" + (f" · {ranks}" if ranks else ""))
            st.text(p["text"])


with tab_search:
    st.subheader("Phase 2: retrieval")
    query = st.text_input("Question (English or Arabic)", "can I return AirPods after opening them?")

    c1, c2, c3 = st.columns([2, 1, 1])
    method = c1.selectbox("Method", list(METHOD_LABELS), format_func=METHOD_LABELS.get)
    use_rerank = c2.toggle("Rerank (cross-encoder)")
    use_rewrite = c3.toggle("Rewrite with Gemini")

    with st.expander("Metadata filters"):
        f1, f2, f3, f4 = st.columns(4)
        doc_type = f1.selectbox("Type", ["any", "policy", "faq", "product"])
        category = f2.text_input("Category", placeholder="e.g. returns, phones")
        max_price = f3.number_input("Max price (EGP, 0 = none)", min_value=0, step=1000)
        include_archived = f4.checkbox("Include archived")
    k = st.slider("Results", 1, 10, 5)
    unique = st.checkbox("One chunk per document", value=True)

    filters = SearchFilters(doc_type=None if doc_type == "any" else doc_type, category=category or None,
                            max_price=max_price or None, include_archived=include_archived)

    view_single, view_compare = st.tabs(["Results", "Compare all methods"])
    if query:
        r = retriever()
        with view_single:
            if use_rewrite:
                with st.spinner("Gemini is rewriting the question..."):
                    plan = r.rewrite(query)
                st.info(f"**Rewritten query:** {plan.query}")
                applied = plan.model_dump(exclude_defaults=True, include={"min_price", "max_price", "include_archived"})
                hints = plan.model_dump(exclude_defaults=True, include={"doc_type", "category", "brand"})
                st.caption(f"Filters applied from the question: {applied or 'none'} · "
                           f"Hints only, not applied: {hints or 'none'}")
            hits = r.search(query, method, k=k, filters=filters, rerank=use_rerank,
                            rewrite=use_rewrite, unique_docs=unique)
            show_hits(hits)
        with view_compare:
            st.caption("Same question and filters, every method side by side (top documents).")
            q = r.rewrite(query).query if use_rewrite else query
            cols = st.columns(3)
            for i, m in enumerate(METHOD_LABELS):
                with cols[i % 3].container(border=True):
                    st.markdown(f"**{METHOD_LABELS[m]}**")
                    for j, h in enumerate(r.search(q, m, k=k, filters=filters, rerank=use_rerank, unique_docs=True), 1):
                        st.write(f"{j}. `{h.doc_id}` {h.properties['title'][:38]}")

# ---------------------------------------------------------------- Evaluation (Phase 2)
with tab_eval:
    findings, report = ROOT / "reports" / "retrieval_findings.md", ROOT / "reports" / "retrieval_eval.md"
    view_findings, view_numbers = st.tabs(["Findings and decisions", "Full numbers"])
    with view_findings:
        if findings.exists():
            st.markdown(findings.read_text(encoding="utf-8"))
    with view_numbers:
        if report.exists():
            st.markdown(report.read_text(encoding="utf-8"))
        else:
            st.info("Run `python scripts/eval_retrieval.py` to create the evaluation report.")

# ---------------------------------------------------------------- SQL
with tab_sql:
    st.subheader("SQLite store database")
    counts = {t: int(sql(f"SELECT COUNT(*) n FROM {t}").n[0])
              for t in ("customers", "products", "orders", "order_items")}
    for col, (name, n) in zip(st.columns(4), counts.items()):
        col.metric(name, n)

    examples = {
        "Top 10 customers by delivered spend": """SELECT c.full_name, c.city, c.loyalty_tier, SUM(o.total_egp) AS spent_egp
FROM orders o JOIN customers c USING (customer_id)
WHERE o.status = 'delivered'
GROUP BY c.customer_id ORDER BY spent_egp DESC LIMIT 10""",
        "Products and stock": "SELECT sku, brand, name, category, price_egp, stock_qty FROM products ORDER BY category, price_egp",
        "Out of stock products": "SELECT sku, brand, name, price_egp FROM products WHERE stock_qty = 0",
        "Orders by status": "SELECT status, COUNT(*) AS orders, SUM(total_egp) AS total_egp FROM orders GROUP BY status ORDER BY orders DESC",
        "Best-selling products": """SELECT p.brand, p.name, SUM(i.quantity) AS units_sold
FROM order_items i JOIN products p USING (sku) JOIN orders o USING (order_id)
WHERE o.status = 'delivered'
GROUP BY p.sku ORDER BY units_sold DESC LIMIT 10""",
    }
    pick = st.selectbox("Example query", list(examples))
    query = st.text_area("SQL (read-only)", examples[pick], height=140)
    try:
        st.dataframe(sql(query), hide_index=True, width="stretch")
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")
