"""A small MCP server that exposes the store's inventory.

MCP (Model Context Protocol) is a standard way to offer tools to any AI
agent. This file is a separate program: the agent starts it, asks "which
tools do you have?", and calls them over stdin/stdout. In a real company
this server would belong to the warehouse team and the agent would only
connect to it.

Run by hand (it waits for an MCP client): python shopmind/mcp_server.py
"""
import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shop.db"

mcp = FastMCP("shopmind-inventory", log_level="WARNING")


@mcp.tool()
def check_stock(product: str) -> str:
    """Check live stock for a product.

    Args:
        product: a SKU such as "SM-PH-004", or part of the product name such as "Redmi Note".

    Returns JSON with sku, name, price_egp, stock_qty and in_stock for every match.
    """
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)  # read-only
    try:
        rows = con.execute(
            """SELECT sku, brand || ' ' || name, price_egp, stock_qty FROM products
               WHERE sku = ? COLLATE NOCASE OR (brand || ' ' || name) LIKE ? LIMIT 5""",
            (product.strip(), f"%{product.strip()}%"),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return json.dumps({"error": f"No product matches '{product}'."})
    return json.dumps([{"sku": s, "name": n, "price_egp": p, "stock_qty": q, "in_stock": q > 0} for s, n, p, q in rows])


if __name__ == "__main__":
    mcp.run(transport="stdio")
