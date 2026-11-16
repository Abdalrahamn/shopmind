"""ShopMind explorer: a local web page to use the assistant and see how every phase works.

Run: streamlit run app.py   (then open http://localhost:8501)

The page has a sidebar with five groups:
    Assistant   chat with the agent
    Overview    what the project is, key results, architecture
    Explore     documents and chunks, the search lab, the SQL database
    Results     evaluation charts and every report
    System      setup check
"""
import asyncio
import html
import json
import os
import queue
import sqlite3
import statistics
import threading
from contextlib import closing

import pandas as pd
import streamlit as st

from shopmind.agent import build_agent, run_turn
from shopmind.config import CACHE_DIR, CHAT_MODEL, DB_PATH, DOCS_DIR, EMBEDDING_MODEL, LLM_PROVIDER, ROOT
from shopmind.documents import chunk_documents, load_documents
from shopmind.generation import Generator
from shopmind.retrieval import Retriever, SearchFilters
from shopmind.tools import UserContext

st.set_page_config(page_title="ShopMind", page_icon="🛒", layout="wide")
MODEL_SHORT = CHAT_MODEL.split("/")[-1]
REPORTS = ROOT / "reports"

# ---------------------------------------------------------------- look and feel
st.markdown("""
<style>
.block-container {padding-top: 3.6rem; padding-bottom: 5rem; max-width: 1180px;}
h1, h2, h3 {letter-spacing: -0.01em;}
/* Arabic and English in the same page: each paragraph takes its own direction */
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li, .sm-auto {unicode-bidi: plaintext; text-align: start;}
[data-testid="stSidebar"] {background: #0F172A;}
[data-testid="stSidebar"] * {color: #E2E8F0;}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {background: rgba(255,255,255,.08);}
[data-testid="stSidebar"] [aria-current="page"] {background: rgba(45,212,191,.18);}
[data-testid="stMetric"] {background: #fff; border: 1px solid #E5E7EB; border-radius: 14px; padding: 14px 16px;}
[data-testid="stMetricLabel"] p {color: #6B7280; font-size: .82rem;}
[data-testid="stChatMessage"] {background: #fff; border: 1px solid #E5E7EB; border-radius: 14px; padding: 14px 16px;}
.sm-hero {background: linear-gradient(120deg, #0F766E 0%, #115E59 55%, #0F172A 100%); color: #fff;
          border-radius: 18px; padding: 26px 30px; margin-bottom: 18px;}
.sm-hero h1 {color: #fff; margin: 0 0 6px 0; font-size: 1.9rem; padding: 0;}
.sm-hero p {color: #D1FAE5; margin: 0; font-size: 1rem;}
.sm-card {background: #fff; border: 1px solid #E5E7EB; border-radius: 14px; padding: 16px 18px; height: 100%;}
.sm-card h4 {margin: 0 0 4px 0; font-size: 1rem; padding: 0;}
.sm-card p {margin: 0; color: #4B5563; font-size: .9rem;}
.sm-chip {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
          margin: 0 6px 4px 0; border: 1px solid transparent;}
.sm-teal {background: #CCFBF1; color: #115E59;} .sm-blue {background: #DBEAFE; color: #1E40AF;}
.sm-amber {background: #FEF3C7; color: #92400E;} .sm-rose {background: #FFE4E6; color: #9F1239;}
.sm-gray {background: #F3F4F6; color: #374151; border-color: #E5E7EB;} .sm-violet {background: #EDE9FE; color: #5B21B6;}
.sm-step {border-left: 3px solid #99F6E4; padding: 2px 0 2px 12px; margin: 0 0 10px 0;}
.sm-step .t {font-weight: 600; font-size: .9rem;} .sm-step .d {color: #6B7280; font-size: .82rem; unicode-bidi: plaintext;}
.sm-side {font-size: .8rem; color: #94A3B8 !important; line-height: 1.5;}
</style>
""", unsafe_allow_html=True)


def chip(text: str, color: str = "gray") -> str:
    return f'<span class="sm-chip sm-{color}">{html.escape(str(text))}</span>'


def page_title(title: str, subtitle: str) -> None:
    st.markdown(f"## {title}")
    st.caption(subtitle)


def card(title: str, body: str) -> str:
    return f'<div class="sm-card"><h4>{html.escape(title)}</h4><p>{html.escape(body)}</p></div>'


# ---------------------------------------------------------------- shared data
@st.cache_resource
def retriever():
    return Retriever()


@st.cache_data
def documents():
    return load_documents(DOCS_DIR)


def sql(query: str, params=()) -> pd.DataFrame:
    with closing(sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)) as con:  # read-only, closed after use
        return pd.read_sql_query(query, con, params=params)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


GOLDEN_RUNS = {  # label -> (runs file, judge file)
    "Gemini lite · first run": ("golden_runs.json", "golden_judge.json"),
    "Gemini lite · after fixes": ("golden_runs_v2.json", "golden_judge_v2.json"),
    "DeepSeek v4.1 flash": ("golden_runs_deepseek.json", "golden_judge_deepseek.json"),
}


def golden_summary() -> pd.DataFrame:
    """Read the saved golden-set runs and count the results (no model calls)."""
    rows = []
    for label, (runs_file, judge_file) in GOLDEN_RUNS.items():
        runs, judge = load_json(CACHE_DIR / runs_file), load_json(CACHE_DIR / judge_file)
        if not runs:
            continue
        judged = [judge[i] for i in runs if i in judge]
        rows.append({
            "Run": label, "Questions": len(runs),
            "Correct %": round(100 * sum(v["correct"] for v in judged) / max(len(judged), 1)),
            "Grounded %": round(100 * sum(v["grounded"] for v in judged) / max(len(judged), 1)),
            "Correct": f"{sum(v['correct'] for v in judged)}/{len(judged)}",
            "Median latency (s)": round(statistics.median(r["latency_s"] for r in runs.values()), 1),
            "Slowest (s)": max(r["latency_s"] for r in runs.values()),
            "Input tokens / question": round(statistics.mean(r["input_tokens"] for r in runs.values())),
        })
    return pd.DataFrame(rows)


def show_report(name: str, missing: str = "") -> None:
    path = REPORTS / name
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.info(missing or f"`reports/{name}` has not been created yet.")


# ---------------------------------------------------------------- the agent (chat page)
@st.cache_resource
def agent_loop():
    """One background event loop for all agent work. The agent's network clients are tied to the
    loop they were created in, so every turn must run in this same loop."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    return loop


@st.cache_resource
def agent():
    # built once; its memory lives as long as this page's server
    return asyncio.run_coroutine_threadsafe(build_agent(), agent_loop()).result()


USERS = {
    "Customer": UserContext("customer", "Khaled Zaki", 20),
    "Staff": UserContext("staff", "Mona (store manager)"),
}
SUGGESTIONS = {
    "Customer": ["What is the return policy?", "عايز موبايل تحت 15 الف ويكون متوفر دلوقتي",
                 "Show my orders", "Cancel my order 1268"],
    "Staff": ["Who are the top 3 customers by spend?", "Which products are out of stock?",
              "How many orders were cancelled?", "What is our total revenue from delivered orders?"],
}
TOOL_LABELS = {  # tool name -> (icon, what it is doing, in plain words)
    "search_store_docs": ("🔎", "Searching the store documents"),
    "query_database": ("🗄️", "Running a SQL query"),
    "get_my_orders": ("📦", "Looking up your orders"),
    "check_stock": ("📊", "Checking live stock (MCP server)"),
    "cancel_order": ("🛑", "Cancelling an order"),
}
ROUTE_CHIPS = {"documents": ("Documents (RAG)", "teal"), "database": ("Database (SQL)", "blue"), "stock": ("Live stock (MCP)", "violet"),
               "action": ("Action", "amber"), "mixed": ("Several sources", "violet"), "none": ("No source", "gray")}


def step_html(step: dict) -> str:
    kind = step["kind"]
    if kind == "call":
        icon, label = TOOL_LABELS.get(step["name"], ("🔧", step["name"]))
        args = ", ".join(f"{k}: {v}" for k, v in step["args"].items()) or "no arguments"
        return f'<div class="sm-step"><div class="t">{icon} {html.escape(label)}</div><div class="d">{html.escape(args)}</div></div>'
    if kind == "result":
        text = " ".join(step["content"].split())
        short = text[:260] + ("…" if len(text) > 260 else "")
        return f'<div class="sm-step"><div class="t">📥 Result</div><div class="d">{html.escape(short)}</div></div>'
    return ('<div class="sm-step" style="border-color:#FCD34D"><div class="t">⏸️ Paused: waiting for a human to approve</div>'
            f'<div class="d">{html.escape(step["name"])} {html.escape(json.dumps(step["args"]))}</div></div>')


def play_turn(user_input, thread_id, ctx):
    """Run one agent turn and draw each step as it arrives (streaming)."""
    record = {"steps": [], "answer": None, "pending": None}
    steps_box = st.status("Thinking…", expanded=True)
    events: queue.Queue = queue.Queue()
    the_agent = agent()

    async def produce():  # runs in the background loop and hands each event to this page
        try:
            async for ev in run_turn(the_agent, user_input, thread_id, ctx):
                events.put(ev)
            events.put(None)
        except Exception as e:
            events.put(e)

    asyncio.run_coroutine_threadsafe(produce(), agent_loop())
    while (ev := events.get()) is not None:
        if isinstance(ev, Exception):
            steps_box.update(label="Failed", state="error")
            st.error(f"The assistant could not finish ({type(ev).__name__}: {str(ev)[:160]}). Please try again.")
            return None
        if ev["type"] == "tool_call":
            step = {"kind": "call", "name": ev["name"], "args": ev["args"]}
            steps_box.update(label=TOOL_LABELS.get(ev["name"], ("", ev["name"]))[1] + "…")
        elif ev["type"] == "tool_result":
            step = {"kind": "result", "name": ev["name"], "content": ev["content"]}
        elif ev["type"] == "approval_needed":
            record["pending"] = ev
            step = {"kind": "pause", "name": ev["name"], "args": ev["args"]}
        else:
            r = ev["reply"]
            record["answer"] = {"text": r.answer, "route": r.route, "sources": r.sources, "model": ev["model"]}
            continue
        record["steps"].append(step)
        steps_box.markdown(step_html(step), unsafe_allow_html=True)
    calls = sum(s["kind"] == "call" for s in record["steps"])
    steps_box.update(label=f"Used {calls} tool call{'s' if calls != 1 else ''}", state="complete", expanded=False)
    return record


def draw_turn(t: dict) -> None:
    with st.chat_message("user", avatar="🧑"):
        st.markdown(t["user"])
    with st.chat_message("assistant", avatar="🛒"):
        calls = sum(s["kind"] == "call" for s in t["steps"])
        if t["steps"]:
            with st.expander(f"How I got this: {calls} tool call{'s' if calls != 1 else ''}"):
                st.markdown("".join(step_html(s) for s in t["steps"]), unsafe_allow_html=True)
        if a := t["answer"]:
            st.markdown(a["text"])
            label, color = ROUTE_CHIPS.get(a["route"], (a["route"], "gray"))
            chips = chip(label, color) + "".join(chip(s, "gray") for s in a["sources"]) + chip(a["model"].split("/")[-1], "gray")
            st.markdown(chips, unsafe_allow_html=True)


def page_chat():
    head, role_col, new_col = st.columns([5, 3, 1.4], vertical_alignment="bottom")
    with head:
        page_title("Chat with ShopMind", "The agent picks a tool for each question: documents, SQL, your orders, "
                                         "live stock, or cancelling an order (which needs your approval).")
    who = role_col.segmented_control("Signed in as", list(USERS), default="Customer", key="who") or "Customer"
    ctx = USERS[who]
    chats = st.session_state.setdefault("chats", {})
    if new_col.button("New chat", icon=":material/add:", use_container_width=True):
        chats.pop(who, None)
    chat = chats.setdefault(who, {"thread": f"ui-{who}-{os.urandom(3).hex()}", "turns": [], "pending": None})

    main, side = st.columns([3, 1.15], gap="large")
    with side:
        with st.container(border=True):
            st.markdown(f"**{ctx.name}**")
            st.markdown(chip(ctx.role, "teal" if ctx.role == "customer" else "blue"), unsafe_allow_html=True)
            if ctx.role == "customer":
                st.caption("Your orders (live from the database)")
                orders = sql("SELECT order_id, status, total_egp FROM orders WHERE customer_id = ? ORDER BY order_date DESC",
                             (ctx.customer_id,))
                colors = {"pending": "amber", "confirmed": "blue", "delivered": "teal", "cancelled": "rose"}
                st.markdown("".join(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                    f'<span><b>#{o.order_id}</b> <span style="color:#6B7280;font-size:.82rem">{o.total_egp:,} EGP</span></span>'
                    f'{chip(o.status, colors.get(o.status, "gray"))}</div>' for o in orders.itertuples()), unsafe_allow_html=True)
            else:
                st.caption("Staff can ask about sales, customers and stock. Customers cannot: the SQL tool checks the role in code.")
        with st.container(border=True):
            st.caption("What the agent can use")
            st.markdown("".join(f'<div class="sm-step" style="margin-bottom:6px"><div class="t">{i} {html.escape(l)}</div></div>'
                                for i, l in [("🔎", "Store documents"), ("🗄️", "SQL database (staff)"), ("📦", "My orders"),
                                             ("📊", "Live stock (MCP)"), ("🛑", "Cancel order (approval)")]),
                        unsafe_allow_html=True)

    def finish(user_text, record):
        if record is None:
            return
        chat["turns"].append({"user": user_text, "steps": record["steps"], "answer": record["answer"]})
        chat["pending"] = record["pending"]
        st.rerun()

    with main:
        for t in chat["turns"]:
            draw_turn(t)

        queued = st.session_state.pop("queued_prompt", None)
        if not chat["turns"] and not queued:
            st.markdown('<div class="sm-card"><h4>👋 Ask me anything about the store</h4>'
                        '<p>English or Arabic. Pick an example or type your own question below.</p></div>',
                        unsafe_allow_html=True)
            st.write("")
            cols = st.columns(2)
            for i, s in enumerate(SUGGESTIONS[who]):
                if cols[i % 2].button(s, key=f"sug-{who}-{i}", use_container_width=True):
                    st.session_state["queued_prompt"] = s
                    st.rerun()

        if chat["pending"]:
            p = chat["pending"]
            with st.container(border=True):
                st.markdown("#### ⏸️ Approval needed")
                st.markdown(f"The assistant wants to run **{p['name']}** with `{json.dumps(p['args'])}`. "
                            "This changes the database, so nothing happens until you decide.")
                b1, b2, _ = st.columns([1, 1, 3])
                approve = b1.button("Approve", type="primary", icon=":material/check:", use_container_width=True)
                reject = b2.button("Reject", icon=":material/close:", use_container_width=True)
            if approve or reject:
                with st.chat_message("assistant", avatar="🛒"):
                    decision = {"type": "approve"} if approve else {"type": "reject", "message": "The user rejected this action."}
                    finish("*(approved the action)*" if approve else "*(rejected the action)*",
                           play_turn(decision, chat["thread"], ctx))

    typed = st.chat_input("Message ShopMind…", disabled=bool(chat["pending"]))
    if prompt := (typed or queued):
        with main:
            with st.chat_message("user", avatar="🧑"):
                st.markdown(prompt)
            with st.chat_message("assistant", avatar="🛒"):
                finish(prompt, play_turn(prompt, chat["thread"], ctx))


# ---------------------------------------------------------------- overview
ARCHITECTURE = """
digraph G {
  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.35; ranksep=0.55;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#CBD5E1", fillcolor="#FFFFFF", margin="0.14,0.08"];
  edge [color="#94A3B8", fontname="Helvetica", fontsize=9, fontcolor="#64748B"];
  user  [label="User\\ncustomer or staff", fillcolor="#F1F5F9"];
  agent [label="Agent\\nLLM + role prompt + memory", fillcolor="#CCFBF1", color="#0F766E", penwidth=1.6];
  search [label="search_store_docs\\nhybrid search + filters"];
  sqlt  [label="query_database\\nread-only SELECT, staff only"];
  mine  [label="get_my_orders"];
  stock [label="check_stock\\nMCP server"];
  human [label="Human approval", shape=diamond, style="filled", fillcolor="#FEF3C7", color="#D97706"];
  cancel [label="cancel_order"];
  weav  [label="Weaviate\\n88 chunks + vectors", shape=cylinder, fillcolor="#EDE9FE", color="#7C3AED"];
  db    [label="SQLite\\ncustomers, products, orders", shape=cylinder, fillcolor="#DBEAFE", color="#2563EB"];
  user -> agent [label="question"];
  agent -> search [label="policies, products"]; agent -> sqlt [label="numbers"];
  agent -> mine [label="my orders"]; agent -> stock [label="in stock?"]; agent -> human [label="cancel"];
  human -> cancel [label="approved"];
  search -> weav; sqlt -> db; mine -> db; stock -> db; cancel -> db;
}
"""


def page_overview():
    st.markdown('<div class="sm-hero"><h1>🛒 ShopMind</h1><p>An AI assistant for an electronics store. It answers from the '
                'store\'s documents (RAG) and its SQL database, and decides which one each question needs.</p></div>',
                unsafe_allow_html=True)

    summary = golden_summary()
    last = summary.iloc[-1] if len(summary) else None
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Golden set, judged correct", last["Correct"] if last is not None else "-", help="25 questions through the real agent, marked by an LLM judge")
    k2.metric("Median answer time", f"{last['Median latency (s)']} s" if last is not None else "-")
    k3.metric("Attacks on the tools refused", "14/14", help="scripts/test_security.py: DELETE, DROP, other customers' orders, SQL injection")
    k4.metric("Tokens per question", f"{last['Input tokens / question']:,}" if last is not None else "-",
              help=f"Average input tokens per question. Model: {MODEL_SHORT} ({LLM_PROVIDER})")

    st.markdown("### How it works")
    st.graphviz_chart(ARCHITECTURE, use_container_width=True)
    st.caption("The agent reads the question and picks a tool. Cancelling an order stops and waits for a person.")

    st.markdown("### What you can do here")
    c = st.columns(3)
    c[0].markdown(card("💬 Chat", "Talk to the assistant as a customer or as staff and watch each tool call."), unsafe_allow_html=True)
    c[1].markdown(card("🔎 Search lab", "Compare BM25, semantic and hybrid search on the same question."), unsafe_allow_html=True)
    c[2].markdown(card("📊 Evaluation", "See how the agent scored on 25 questions, and every failure we found."), unsafe_allow_html=True)
    st.write("")
    l = st.columns(3)
    l[0].page_link(PAGES["chat"], label="Open the chat", icon=":material/chat:")
    l[1].page_link(PAGES["search"], label="Open the search lab", icon=":material/search:")
    l[2].page_link(PAGES["evaluation"], label="Open the evaluation", icon=":material/monitoring:")

    st.markdown("### Project phases")
    phases = [("0", "Setup", "environment, keys, Weaviate, tracing"), ("1", "Data and indexing", "40 documents, 88 chunks, SQLite store"),
              ("2", "Retrieval", "BM25, semantic, hybrid, filters, rewriting"), ("3", "Generation", "citations and \"I don't know\""),
              ("4", "Agent", "tools, MCP, memory, human approval"), ("5", "Evaluation", "golden set, judge, security, cost"),
              ("6", "Deliverables", "diagram, demo, report, decisions")]
    for col, (n, name, what) in zip(st.columns(len(phases)), phases):
        col.markdown(f'<div class="sm-card" style="padding:12px"><span class="sm-chip sm-teal">✓ Phase {n}</span>'
                     f'<h4 style="font-size:.9rem;margin-top:6px">{name}</h4><p style="font-size:.78rem">{what}</p></div>',
                     unsafe_allow_html=True)


# ---------------------------------------------------------------- explore: documents
def page_documents():
    docs = documents()
    chunks = chunk_documents(docs)
    page_title("Documents and chunks", "The store's knowledge: policies, FAQs and product pages, and how they are cut into chunks for search.")
    m = st.columns(4)
    m[0].metric("Documents", len(docs))
    m[1].metric("Chunks", len(chunks))
    m[2].metric("Chunk size", "800 chars", help="with 120 characters of overlap, after splitting by Markdown section")
    m[3].metric("Embedding size", "384", help=EMBEDDING_MODEL)

    table = pd.DataFrame([{k: d.metadata.get(k) for k in
                           ("doc_id", "title", "doc_type", "category", "status", "updated_at", "price_egp")} for d in docs])
    kind = st.segmented_control("Type", ["all", "policy", "faq", "product"], default="all")
    if kind and kind != "all":
        table = table[table.doc_type == kind]
    st.dataframe(table, hide_index=True, use_container_width=True, height=280)

    ids = list(table.doc_id)
    if not ids:
        return
    choice = st.selectbox("Open a document", ids, format_func=lambda i: f"{i} · {table[table.doc_id == i].title.iloc[0]}")
    doc = next(d for d in docs if d.metadata["doc_id"] == choice)
    its_chunks = [c for c in chunks if c.metadata["doc_id"] == choice]
    view_doc, view_chunks, view_meta = st.tabs(["Document", f"Chunks ({len(its_chunks)})", "Metadata"])
    with view_doc:
        with st.container(border=True):
            st.markdown(doc.page_content)
    with view_chunks:
        st.caption("This is what search really sees: each box is stored in Weaviate with its own vector.")
        for c in its_chunks:
            with st.container(border=True):
                st.markdown(chip(f"chunk {c.metadata['chunk_index']}", "teal") + chip(f"{len(c.page_content)} characters"), unsafe_allow_html=True)
                st.text(c.page_content)
    with view_meta:
        st.caption("Metadata is stored with every chunk and used for filters (type, category, price, archived).")
        st.json(dict(doc.metadata))


# ---------------------------------------------------------------- explore: search lab
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
        with st.container(border=True):
            chips = chip(f"#{i}", "teal") + chip(p["doc_id"], "blue") + chip(p["doc_type"]) + chip(f"score {h.score:.3f}")
            if p["status"] == "archived":
                chips += chip("archived", "rose")
            chips += "".join(chip(f"{k.replace('_', ' ')} {v}", "violet") for k, v in h.extra.items()
                             if k.endswith("rank") or k == "before_rerank")
            st.markdown(f"**{p['title']}**  \n{chips}", unsafe_allow_html=True)
            st.caption(f"section: {p['section']}")
            with st.expander("Show text", expanded=i == 1):
                st.text(p["text"])


def page_search():
    page_title("Search lab", "Try each retrieval method from Phase 2 on the same question and see what comes back.")
    query = st.text_input("Question (English or Arabic)", "can I return AirPods after opening them?")
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1], vertical_alignment="bottom")
    method = c1.selectbox("Method", list(METHOD_LABELS), format_func=METHOD_LABELS.get)
    k = c2.number_input("Results", 1, 10, 5)
    use_rewrite = c3.toggle("Rewrite query", help="A model rewrites the question into a short English search query first")
    use_rerank = c4.toggle("Rerank", help="A cross-encoder re-orders the results (slower; it did not help on this data)")
    with st.expander("Metadata filters"):
        f1, f2, f3, f4 = st.columns(4, vertical_alignment="bottom")
        doc_type = f1.selectbox("Type", ["any", "policy", "faq", "product"])
        category = f2.text_input("Category", placeholder="e.g. returns, phones")
        max_price = f3.number_input("Max price (EGP, 0 = none)", min_value=0, step=1000)
        include_archived = f4.checkbox("Include archived")
        unique = st.checkbox("One chunk per document", value=True)
    filters = SearchFilters(doc_type=None if doc_type == "any" else doc_type, category=category or None,
                            max_price=max_price or None, include_archived=include_archived)
    if not query:
        return
    r = retriever()
    view_single, view_compare = st.tabs(["Results", "Compare all methods"])
    with view_single:
        if use_rewrite:
            with st.spinner("Rewriting the question…"):
                plan = r.rewrite(query)
            applied = plan.model_dump(exclude_defaults=True, include={"min_price", "max_price", "include_archived"})
            hints = plan.model_dump(exclude_defaults=True, include={"doc_type", "category", "brand"})
            st.info(f"**Rewritten query:** {plan.query}\n\nFilters applied from the question: {applied or 'none'} · "
                    f"hints only, not applied: {hints or 'none'}")
        show_hits(r.search(query, method, k=k, filters=filters, rerank=use_rerank, rewrite=use_rewrite, unique_docs=unique))
    with view_compare:
        st.caption("Same question and filters, every method side by side (top documents).")
        q = r.rewrite(query).query if use_rewrite else query
        cols = st.columns(3)
        for i, m in enumerate(METHOD_LABELS):
            with cols[i % 3].container(border=True):
                st.markdown(f"**{METHOD_LABELS[m]}**")
                for j, h in enumerate(r.search(q, m, k=k, filters=filters, rerank=use_rerank, unique_docs=True), 1):
                    st.markdown(f"{j}. `{h.doc_id}` {h.properties['title'][:36]}")

    st.divider()
    st.markdown("#### Ask with the fixed RAG pipeline (Phase 3)")
    st.caption("Search, then the model answers only from the chunks, with citations. No agent, no tools.")
    with st.form("ask"):
        question = st.text_input("Your question", placeholder="how much is delivery to Alexandria?")
        submitted = st.form_submit_button("Ask", type="primary")
    if submitted and question:
        try:
            with st.spinner("Searching and writing the answer…"):
                res = Generator(r).answer(question)
        except Exception as e:
            st.error(f"The model could not answer right now ({type(e).__name__}). Please try again.")
            return
        (st.success if res.answerable else st.warning)(res.answer)
        if not res.answerable:
            st.caption("The sources did not contain the answer, so ShopMind did not guess.")
        m = st.columns(4)
        m[0].metric("Citations", ", ".join(res.citations) or "none")
        m[1].metric("Latency", "cached" if res.cached else f"{res.latency_s} s")
        m[2].metric("Tokens in / out", f"{res.input_tokens} / {res.output_tokens}")
        m[3].metric("Model", res.model.split("/")[-1].replace("gemini-", ""))
        for h in res.hits:
            used = "✅ cited" if h.doc_id in res.citations else "not cited"
            with st.expander(f"{h.doc_id} · {h.properties['title']} · {used}"):
                st.text(h.text)


# ---------------------------------------------------------------- explore: database
SQL_EXAMPLES = {
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


def page_database():
    page_title("Store database", "The SQLite database the agent queries: customers, products, orders. Everything here is read-only.")
    counts = {t: int(sql(f"SELECT COUNT(*) n FROM {t}").n[0]) for t in ("customers", "products", "orders", "order_items")}
    for col, (name, n) in zip(st.columns(4), counts.items()):
        col.metric(name.replace("_", " ").title(), f"{n:,}")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Orders by status**")
        st.bar_chart(sql("SELECT status, COUNT(*) AS orders FROM orders GROUP BY status ORDER BY orders DESC"),
                     x="status", y="orders", color="#0F766E", height=260, horizontal=True)
    with right:
        st.markdown("**Stock by product (units)**")
        st.bar_chart(sql("SELECT name, stock_qty FROM products ORDER BY stock_qty DESC LIMIT 12"),
                     x="name", y="stock_qty", color="#2563EB", height=260, horizontal=True)

    st.markdown("#### SQL console")
    pick = st.selectbox("Example query", list(SQL_EXAMPLES))
    query = st.text_area("SQL (read-only connection: writes are impossible)", SQL_EXAMPLES[pick], height=130)
    try:
        st.dataframe(sql(query), hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- results: evaluation
RETRIEVAL_RESULTS = pd.DataFrame(  # Phase 2, 28 labelled questions (reports/retrieval_findings.md)
    [("BM25 from scratch", 0.75, 0.74), ("BM25 (Weaviate)", 0.77, 0.77), ("Semantic", 0.86, 0.80), ("Hybrid RRF", 0.89, 0.87),
     ("Hybrid + reranker", 0.82, 0.79), ("Rewrite + Hybrid", 1.00, 0.98)], columns=["Method", "Recall@3", "MRR"])


def golden_questions(label: str) -> pd.DataFrame:
    runs_file, judge_file = GOLDEN_RUNS[label]
    runs, judge = load_json(CACHE_DIR / runs_file), load_json(CACHE_DIR / judge_file)
    golden = json.loads((ROOT / "data" / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    mark = lambda v: "✅" if v else "❌"  # noqa: E731
    rows = []
    for q in golden:
        if (r := runs.get(q["id"])) is None:
            continue
        v = judge.get(q["id"])
        rows.append({"id": q["id"], "Type": q["type"], "Question": q["question"],
                     "Tools": ", ".join(dict.fromkeys(t["name"] for t in r["tools"])) or "none",
                     "Correct": mark(v["correct"]) if v else "-", "Grounded": mark(v["grounded"]) if v else "-",
                     "Seconds": r["latency_s"], "Answer": r["answer"], "Judge's reason": v["reason"] if v else ""})
    return pd.DataFrame(rows)


def page_evaluation():
    page_title("Evaluation", "How well the retrieval and the whole agent work, measured on fixed sets of questions.")
    tab_sum, tab_q, tab_fail, tab_sec = st.tabs(["Summary", "Golden set, question by question", "Failure cases", "Security"])

    with tab_sum:
        summary = golden_summary()
        st.markdown("#### The agent on the golden set (25 questions)")
        st.caption("The same questions, three runs: before the fixes, after the fixes, and after moving to DeepSeek.")
        if len(summary):
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("**Judged correct (%)**")
                st.bar_chart(summary, x="Run", y="Correct %", color="#0F766E", height=240, horizontal=True)
            with c2:
                st.markdown("**Median answer time (seconds)**")
                st.bar_chart(summary, x="Run", y="Median latency (s)", color="#D97706", height=240, horizontal=True)
            st.dataframe(summary.drop(columns=["Correct %"]), hide_index=True, use_container_width=True)
        st.markdown("#### Retrieval methods (Phase 2, 28 questions)")
        st.caption("Recall@3: share of the documents holding the answer that were found in the top 3.")
        c1, c2 = st.columns([1.3, 1], gap="large")
        with c1:
            st.bar_chart(RETRIEVAL_RESULTS, x="Method", y="Recall@3", color="#2563EB", height=280, horizontal=True)
        with c2:
            st.dataframe(RETRIEVAL_RESULTS, hide_index=True, use_container_width=True)
            st.caption("Chosen: query rewriting + hybrid search. The reranker made results worse and stays off.")

    with tab_q:
        label = st.selectbox("Run", list(GOLDEN_RUNS), index=len(GOLDEN_RUNS) - 1)
        table = golden_questions(label)
        if table.empty:
            st.info("This run has not been done yet.")
        else:
            only_bad = st.toggle("Only show answers the judge did not fully pass")
            if only_bad:
                table = table[(table.Correct == "❌") | (table.Grounded == "❌")]
            st.dataframe(table, hide_index=True, use_container_width=True, height=520,
                         column_config={"Question": st.column_config.TextColumn(width="medium"),
                                        "Answer": st.column_config.TextColumn(width="large"),
                                        "Judge's reason": st.column_config.TextColumn(width="large")})
            st.caption("Click a cell to read the full text.")
    with tab_fail:
        show_report("failure_cases.md")
    with tab_sec:
        show_report("security_tests.md")
        st.divider()
        show_report("security_doc_injection.md")


REPORT_FILES = {
    "Evaluation report (one page)": "evaluation_report.md", "Decisions log": "decisions.md",
    "Demo: the four acceptance questions": "agent_demo.md", "Failure cases": "failure_cases.md",
    "Cost, latency and tracing": "production_notes.md", "Golden set · DeepSeek": "golden_eval_deepseek.md",
    "Golden set · Gemini after fixes": "golden_eval_v2.md", "Golden set · first run": "golden_eval.md",
    "Retrieval findings (Phase 2)": "retrieval_findings.md", "Retrieval numbers (Phase 2)": "retrieval_eval.md",
    "Generation findings (Phase 3)": "generation_findings.md", "Generation numbers (Phase 3)": "generation_eval.md",
    "Agent findings (Phase 4)": "agent_findings.md", "Security tests": "security_tests.md",
    "Injection inside a document": "security_doc_injection.md",
}


def page_reports():
    page_title("Reports", "Every report written during the project, in one place.")
    pick = st.selectbox("Report", list(REPORT_FILES))
    st.caption(f"File: `reports/{REPORT_FILES[pick]}`")
    with st.container(border=True):
        show_report(REPORT_FILES[pick])


# ---------------------------------------------------------------- system
def page_setup():
    page_title("Setup check", "Are all the parts the project needs working?")
    cols = st.columns(4)
    key_name = "OPENROUTER_API_KEY" if LLM_PROVIDER == "openrouter" else "GOOGLE_API_KEY"
    if os.getenv(key_name):
        cols[0].success(f"**LLM · {LLM_PROVIDER}**\n\nkey found · `{MODEL_SHORT}`")
    else:
        cols[0].error(f"**LLM · {LLM_PROVIDER}**\n\n{key_name} missing")
    if os.getenv("LANGSMITH_API_KEY"):
        cols[1].success(f"**LangSmith tracing**\n\nproject `{os.getenv('LANGSMITH_PROJECT')}`")
    else:
        cols[1].error("**LangSmith tracing**\n\nLANGSMITH_API_KEY missing")
    try:
        total = retriever().collection.aggregate.over_all(total_count=True).total_count
        cols[2].success(f"**Weaviate**\n\nready · {total} chunks stored")
    except Exception as e:
        cols[2].error(f"**Weaviate**\n\n{type(e).__name__}")
    cols[3].success(f"**Embeddings**\n\n`{EMBEDDING_MODEL.split('/')[-1]}` · 384 dims")

    if st.button("Send a test message to the model", type="primary"):
        from shopmind.llm import chat_model
        try:
            with st.spinner(f"Asking {MODEL_SHORT}…"):
                reply = chat_model(CHAT_MODEL).invoke("Say hello in Egyptian Arabic in one short sentence")
            st.info(reply.text)
            st.caption("This call is now visible in LangSmith → project shopmind.")
        except Exception as e:
            st.error(f"The model did not answer ({type(e).__name__}: {str(e)[:160]}).")


# ---------------------------------------------------------------- navigation
PAGES = {
    "chat": st.Page(page_chat, title="Chat", icon=":material/chat:", url_path="chat", default=True),
    "overview": st.Page(page_overview, title="Overview", icon=":material/home:", url_path="overview"),
    "documents": st.Page(page_documents, title="Documents and chunks", icon=":material/description:", url_path="documents"),
    "search": st.Page(page_search, title="Search lab", icon=":material/search:", url_path="search"),
    "database": st.Page(page_database, title="Database", icon=":material/database:", url_path="database"),
    "evaluation": st.Page(page_evaluation, title="Evaluation", icon=":material/monitoring:", url_path="evaluation"),
    "reports": st.Page(page_reports, title="Reports", icon=":material/article:", url_path="reports"),
    "setup": st.Page(page_setup, title="Setup check", icon=":material/settings:", url_path="setup"),
}
nav = st.navigation({
    "Assistant": [PAGES["chat"]],
    "Project": [PAGES["overview"]],
    "Explore": [PAGES["documents"], PAGES["search"], PAGES["database"]],
    "Results": [PAGES["evaluation"], PAGES["reports"]],
    "System": [PAGES["setup"]],
})
with st.sidebar:
    st.markdown(f'<div class="sm-side">ShopMind · capstone project<br>Model: {html.escape(MODEL_SHORT)}<br>Provider: {html.escape(LLM_PROVIDER)}</div>',
                unsafe_allow_html=True)
nav.run()
