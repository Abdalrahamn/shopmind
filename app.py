"""ShopMind explorer: a local page to see what Phases 0 and 1 built.

Run: streamlit run app.py   (then open http://localhost:8501)
"""
import os
import sqlite3

import pandas as pd
import streamlit as st
import weaviate
from sentence_transformers import SentenceTransformer
from weaviate.classes.query import Filter, MetadataQuery

from shopmind.config import DB_PATH, DOCS_DIR, EMBEDDING_MODEL, GEMINI_MODEL, WEAVIATE_COLLECTION
from shopmind.documents import chunk_documents, load_documents

st.set_page_config(page_title="ShopMind Explorer", page_icon="🛒", layout="wide")


@st.cache_resource
def embedder():
    return SentenceTransformer(EMBEDDING_MODEL)


@st.cache_resource
def weaviate_client():
    return weaviate.connect_to_local()


@st.cache_data
def documents():
    return load_documents(DOCS_DIR)


def sql(query: str, params=()) -> pd.DataFrame:
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:  # read-only
        return pd.read_sql_query(query, con, params=params)


st.title("🛒 ShopMind Explorer")
st.caption("Everything built in Phase 0 (setup) and Phase 1 (data and indexing).")

tab_setup, tab_docs, tab_chunks, tab_search, tab_sql = st.tabs(
    ["⚙️ Setup", "📄 Documents", "✂️ Chunks", "🔎 Search", "🗄️ SQL database"]
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
        client = weaviate_client()
        total = client.collections.get(WEAVIATE_COLLECTION).aggregate.over_all(total_count=True).total_count
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
    st.dataframe(table, hide_index=True, use_container_width=True)

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

# ---------------------------------------------------------------- Search
with tab_search:
    st.subheader("Search the Weaviate index")
    query = st.text_input("Question", "how many days do I have to send back headphones I already opened?")
    c1, c2, c3, c4 = st.columns(4)
    mode = c1.radio("Method", ["Semantic (meaning)", "Keyword (BM25)"])
    doc_type = c2.selectbox("Filter: type", ["any", "policy", "faq", "product"])
    active_only = c3.checkbox("Only active (hide archived)")
    max_price = c4.number_input("Filter: max price (EGP, 0 = none)", min_value=0, step=1000)
    k = st.slider("Results", 1, 10, 5)

    filters = []
    if doc_type != "any":
        filters.append(Filter.by_property("doc_type").equal(doc_type))
    if active_only:
        filters.append(Filter.by_property("status").equal("active"))
    if max_price:
        filters.append(Filter.by_property("price_egp").less_than(max_price))
    combined = Filter.all_of(filters) if filters else None

    if query:
        collection = weaviate_client().collections.get(WEAVIATE_COLLECTION)
        if mode.startswith("Semantic"):
            vector = embedder().encode(query, normalize_embeddings=True).tolist()
            res = collection.query.near_vector(vector, limit=k, filters=combined,
                                               return_metadata=MetadataQuery(distance=True))
            score = lambda o: f"similarity {1 - o.metadata.distance:.2f}"  # noqa: E731
        else:
            res = collection.query.bm25(query, limit=k, filters=combined,
                                        return_metadata=MetadataQuery(score=True))
            score = lambda o: f"BM25 score {o.metadata.score:.2f}"  # noqa: E731

        if not res.objects:
            st.warning("No results.")
        for i, o in enumerate(res.objects, 1):
            p = o.properties
            badge = " 🗄️ ARCHIVED" if p["status"] == "archived" else ""
            with st.expander(f"{i}. {p['doc_id']} · {p['title']}{badge} · {score(o)}", expanded=i <= 2):
                st.caption(f"{p['doc_type']} · {p['category']} · section: {p['section']}")
                st.text(p["text"])

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
        st.dataframe(sql(query), hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")
