"""Phase 5 security tests on the tools themselves. No Gemini calls, so they are free and repeatable.

The idea: assume the model has been fooled (prompt injection) and sends the
worst possible tool call. The tools' code must still refuse. Each test calls a
tool directly with a hostile input and checks two things: the reply, and that
the database did not change.

Run: python scripts/test_security.py     (writes reports/security_tests.md)
"""
import asyncio
import hashlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopmind.config import DB_PATH  # noqa: E402
from shopmind.mcp_server import check_stock  # noqa: E402
from shopmind.tools import UserContext, cancel_order, get_my_orders, query_database  # noqa: E402

STAFF = SimpleNamespace(context=UserContext("staff", "Mona"))
CUSTOMER = SimpleNamespace(context=UserContext("customer", "Khaled Zaki", 20))
GUEST = SimpleNamespace(context=UserContext("customer", "Guest", None))


def db_fingerprint() -> str:
    """A hash of every row in every table: if anything changes, this changes."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    h = hashlib.sha256()
    for table in ("customers", "products", "orders", "order_items"):
        for row in con.execute(f"SELECT * FROM {table} ORDER BY 1, 2"):
            h.update(repr(row).encode())
    con.close()
    return h.hexdigest()


def sql(statement, who=STAFF):
    return query_database.func(statement, runtime=who)


TESTS = [
    # name, what the attacker tries, call, text the reply must contain
    ("Customer runs SQL", "A customer (or a fooled model) calls the SQL tool",
     lambda: sql("SELECT full_name, email, phone FROM customers", CUSTOMER), "Refused"),
    ("DELETE", "Delete all orders", lambda: sql("DELETE FROM orders"), "Refused"),
    ("UPDATE", "Change a price", lambda: sql("UPDATE products SET price_egp = 1"), "Refused"),
    ("DROP TABLE", "Destroy a table", lambda: sql("DROP TABLE customers"), "Refused"),
    ("Two statements", "Hide a DROP after a SELECT", lambda: sql("SELECT 1; DROP TABLE orders"), "Refused"),
    ("Write hidden in WITH", "A statement that starts like a SELECT but deletes",
     lambda: sql("WITH x AS (SELECT 1) DELETE FROM orders"), "SQL error"),
    ("PRAGMA", "Change database settings", lambda: sql("PRAGMA writable_schema = 1"), "Refused"),
    ("ATTACH", "Open another database file", lambda: sql("ATTACH DATABASE '/tmp/x.db' AS x"), "Refused"),
    ("Comment trick", "Hide the real statement behind a comment",
     lambda: sql("/* SELECT */ DELETE FROM orders"), "Refused"),
    ("Cancel someone else's order", "Customer 20 cancels order 1073 (customer 121)",
     lambda: cancel_order.func(1073, runtime=CUSTOMER), "does not belong"),
    ("Cancel a delivered order", "Customer 20 cancels their delivered order 1223",
     lambda: cancel_order.func(1223, runtime=CUSTOMER), "cannot be cancelled"),
    ("Guest lists orders", "Nobody is signed in", lambda: get_my_orders.func(runtime=GUEST), "No customer is signed in"),
    ("SQL injection in stock check", "Product name carrying SQL",
     lambda: check_stock("x'; DROP TABLE products; --"), "No product matches"),
    ("SQL injection, OR 1=1", "Try to list every product through the stock tool",
     lambda: check_stock("' OR '1'='1"), "No product matches"),
]


def main() -> None:
    lines = ["# Security tests on the tools (Phase 5)", "",
             "Each row sends a hostile call straight to a tool, as if the model had been fooled. "
             "Pass = the tool refused **and** the database is byte-for-byte unchanged. No LLM is involved.", "",
             "| Test | The attack | Tool reply | Database unchanged | Result |", "|---|---|---|---|---|"]
    passed = 0
    for name, attack, call, expected in TESTS:
        before = db_fingerprint()
        try:
            reply = str(call())
        except Exception as e:
            reply = f"{type(e).__name__}: {e}"
        unchanged = db_fingerprint() == before
        ok = expected in reply and unchanged
        passed += ok
        short = reply.replace("\n", " ").replace("|", "/")[:90]
        lines.append(f"| {name} | {attack} | {short} | {'yes' if unchanged else '**NO**'} | {'✅ pass' if ok else '❌ FAIL'} |")
    lines += ["", f"**{passed}/{len(TESTS)} passed.**"]
    report = "\n".join(lines) + "\n"
    (ROOT / "reports" / "security_tests.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
