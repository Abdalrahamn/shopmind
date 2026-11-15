"""The agent's own tools (the stock tool lives in the MCP server).

A tool is a normal Python function plus a description. The model never runs
code: it reads the descriptions, decides which tool fits the question, and
replies with the tool's name and arguments. LangChain then runs the function
and gives the result back to the model.

Safety rules live here in code, not in the prompt, because a prompt can be
talked around and code cannot:
  - the database tool only accepts a single SELECT on a read-only connection
  - customers cannot run SQL at all; they get `get_my_orders` instead
  - `cancel_order` checks who owns the order and its status before changing it
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

from langchain.tools import ToolRuntime, tool

from shopmind.config import DB_PATH
from shopmind.retrieval import Retriever, SearchFilters


@dataclass
class UserContext:
    """Who is talking to the agent. Set by the app, never by the model."""
    role: Literal["customer", "staff"] = "customer"
    name: str = "Guest"
    customer_id: int | None = None


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


@tool
def search_store_docs(query: str, doc_type: Literal["policy", "faq", "product"] | None = None,
                      product_category: Literal["phones", "laptops", "audio", "accessories", "smart-home",
                                                "gaming"] | None = None,
                      max_price_egp: float | None = None, runtime: ToolRuntime[UserContext] = None) -> str:
    """Search the store's documents: policies (returns, shipping, warranty, payment, instalments,
    cancellation, loyalty), FAQs, and product pages with specs and prices.

    Use this for any question about rules, how things work, or which product fits a need.

    Args:
        query: short English search query using store words, e.g. "return window opened product".
        doc_type: only set it when the customer clearly wants one kind, e.g. "product" for product advice.
        product_category: only when the customer names the kind of product they want, e.g. "phones".
        max_price_egp: maximum product price in EGP, only when the customer gives a budget.
    """
    filters = SearchFilters(doc_type=doc_type, category=product_category, max_price=max_price_egp)
    retriever = get_retriever()
    hits = retriever.search(query, method="hybrid", k=5, filters=filters)

    # Safety net found in the Phase 5 evaluation: a model sometimes drops the key word when it writes
    # the query ("can I return the Pixel 10a?" became "return policy"), so the product page was never
    # found and the answer was wrong. We also search with the customer's own words and add what is new.
    question = _last_user_message(runtime)
    if question and question != query and not re.search("[\u0600-\u06FF]", question):  # embeddings are English-only
        seen = {h.id for h in hits}
        hits += [h for h in retriever.search(question, method="hybrid", k=3, filters=filters) if h.id not in seen]

    if not hits:
        return "No documents matched. Tell the customer you do not have this information."
    return "\n\n".join(f"[{h.doc_id}] {h.properties['title']}\n{h.text}" for h in hits)


def _last_user_message(runtime) -> str:
    messages = (getattr(runtime, "state", None) or {}).get("messages", [])
    return next((str(m.content) for m in reversed(messages) if m.type == "human"), "")


def _read_only():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _table(cursor, rows) -> str:
    cols = [c[0] for c in cursor.description]
    lines = [" | ".join(cols)] + [" | ".join(str(v) for v in row) for row in rows]
    return "\n".join(lines)


@tool
def query_database(sql: str, runtime: ToolRuntime[UserContext]) -> str:
    """Run one read-only SQL SELECT on the store database (SQLite). Staff only.

    Use this for numbers and records: sales, top customers, order counts, stock reports.

    Tables:
      customers(customer_id, full_name, email, phone, city, joined_at, loyalty_tier)
      products(sku, name, brand, category, price_egp, warranty_months, clearance, stock_qty)
      orders(order_id, customer_id, order_date, status, payment_method, shipping_city, shipping_fee, total_egp)
        status is one of: pending, confirmed, shipped, delivered, cancelled, returned
      order_items(order_id, sku, quantity, unit_price)
    Count revenue and spending from orders with status = 'delivered'.
    """
    if runtime.context.role != "staff":
        return "Refused: only staff can query the database. For a customer's own orders use get_my_orders."
    statement = sql.strip().rstrip(";")
    if ";" in statement or not re.match(r"(?is)^\s*(select|with)\b", statement):
        return "Refused: only a single SELECT statement is allowed."
    con = _read_only()
    try:
        cur = con.execute(statement)
        rows = cur.fetchmany(50)
        return _table(cur, rows) if rows else "The query returned no rows."
    except sqlite3.Error as e:
        return f"SQL error: {e}. Fix the query and try again."
    finally:
        con.close()


@tool
def get_my_orders(runtime: ToolRuntime[UserContext]) -> str:
    """List the current customer's own orders (id, date, status, total, items), newest first."""
    cid = runtime.context.customer_id
    if cid is None:
        return "No customer is signed in, so there are no orders to show."
    con = _read_only()
    try:
        cur = con.execute(
            """SELECT o.order_id, o.order_date, o.status, o.total_egp,
                      GROUP_CONCAT(p.brand || ' ' || p.name || ' x' || i.quantity, ', ') AS items
               FROM orders o JOIN order_items i USING (order_id) JOIN products p USING (sku)
               WHERE o.customer_id = ? GROUP BY o.order_id ORDER BY o.order_date DESC LIMIT 10""", (cid,))
        rows = cur.fetchall()
        return _table(cur, rows) if rows else "This customer has no orders."
    finally:
        con.close()


@tool
def cancel_order(order_id: int, runtime: ToolRuntime[UserContext]) -> str:
    """Cancel an order. This changes the database, so a human must approve it first.

    Only orders with status pending or confirmed can be cancelled (Order Cancellation Policy).
    """
    ctx = runtime.context
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute("SELECT customer_id, status FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return f"Order {order_id} does not exist."
        owner, status = row
        if ctx.role == "customer" and owner != ctx.customer_id:
            return f"Refused: order {order_id} does not belong to this customer."
        if status not in ("pending", "confirmed"):
            return (f"Order {order_id} cannot be cancelled because its status is '{status}'. "
                    "Shipped orders must be refused at the door or returned after delivery.")
        con.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
        con.commit()
        return f"Order {order_id} is now cancelled. Prepaid orders are refunded to the original payment method."
    finally:
        con.close()


LOCAL_TOOLS = [search_store_docs, query_database, get_my_orders, cancel_order]
