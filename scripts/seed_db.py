"""Build data/shop.db: customers, products, orders and order items.

Products are read from the product documents, so the SQL catalogue and the
RAG documents always share the same SKUs and prices. The data is random but
seeded, so every run produces the same database.

Run: python scripts/seed_db.py
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shopmind.config import DB_PATH, DOCS_DIR  # noqa: E402
from shopmind.documents import load_documents  # noqa: E402

rng = random.Random(42)

FIRST = ["Ahmed", "Mohamed", "Mahmoud", "Omar", "Youssef", "Mostafa", "Karim", "Hassan", "Ali", "Khaled",
         "Mariam", "Nour", "Salma", "Farida", "Habiba", "Aya", "Yasmin", "Laila", "Rana", "Hana"]
LAST = ["Hassan", "Ibrahim", "Mahfouz", "Saeed", "Farouk", "Mansour", "Fathy", "Abdelaziz", "Gamal", "Naguib",
        "Sherif", "Kamal", "Soliman", "Zaki", "Ragab"]
CITIES = [("Cairo", 40), ("Giza", 25), ("Alexandria", 15), ("Mansoura", 6), ("Tanta", 4),
          ("Ismailia", 3), ("Assiut", 3), ("Hurghada", 2), ("Luxor", 2)]
PAYMENTS = [("card", 45), ("cod", 30), ("wallet", 15), ("instalments", 10)]
STATUSES = [("delivered", 70), ("shipped", 8), ("confirmed", 5), ("pending", 5), ("cancelled", 7), ("returned", 5)]

SCHEMA = """
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT NOT NULL,
    city          TEXT NOT NULL,
    joined_at     DATE NOT NULL,
    loyalty_tier  TEXT NOT NULL CHECK (loyalty_tier IN ('standard', 'gold'))
);
CREATE TABLE products (
    sku              TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    brand            TEXT NOT NULL,
    category         TEXT NOT NULL,
    price_egp        INTEGER NOT NULL,
    warranty_months  INTEGER NOT NULL,
    clearance        INTEGER NOT NULL DEFAULT 0,
    stock_qty        INTEGER NOT NULL
);
CREATE TABLE orders (
    order_id        INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date      DATE NOT NULL,
    status          TEXT NOT NULL,
    payment_method  TEXT NOT NULL,
    shipping_city   TEXT NOT NULL,
    shipping_fee    INTEGER NOT NULL,
    total_egp       INTEGER NOT NULL
);
CREATE TABLE order_items (
    order_id    INTEGER NOT NULL REFERENCES orders(order_id),
    sku         TEXT NOT NULL REFERENCES products(sku),
    quantity    INTEGER NOT NULL,
    unit_price  INTEGER NOT NULL,
    PRIMARY KEY (order_id, sku)
);
"""


def pick(weighted):
    items, weights = zip(*weighted)
    return rng.choices(items, weights=weights)[0]


def shipping_fee(city: str, subtotal: int) -> int:
    # Same rules as the Shipping and Delivery Policy (POL-002).
    if city in ("Cairo", "Giza"):
        return 0 if subtotal >= 2000 else 50
    return 0 if subtotal >= 5000 else 75


def main() -> None:
    products = [d.metadata for d in load_documents(DOCS_DIR) if d.metadata["doc_type"] == "product"]

    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    for p in products:
        stock = 0 if rng.random() < 0.15 else rng.randint(1, 60)  # some products sold out
        con.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)",
                    (p["sku"], p["title"].removeprefix(p["brand"] + " "), p["brand"], p["category"],
                     p["price_egp"], p["warranty_months"], int(p["clearance"]), stock))

    customers = []
    for cid in range(1, 201):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        city = pick(CITIES)
        joined = date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))
        customers.append((cid, city, joined))
        con.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
                    (cid, f"{first} {last}", f"{first.lower()}.{last.lower()}{cid}@example.com",
                     f"01{rng.choice('0125')}{rng.randint(10_000_000, 99_999_999)}", city,
                     joined.isoformat(), "standard"))

    today = date(2026, 11, 8)
    for oid in range(1001, 1401):
        cid, city, joined = rng.choice(customers)
        order_date = joined + timedelta(days=rng.randint(0, (today - joined).days))
        status = pick(STATUSES)
        if (today - order_date).days < 3 and status == "delivered":
            status = "shipped"
        items = rng.sample(products, k=rng.choice([1, 1, 1, 2, 2, 3]))
        subtotal = 0
        for p in items:
            qty = 1 if p["price_egp"] > 5000 else rng.randint(1, 3)
            subtotal += qty * p["price_egp"]
            con.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid, p["sku"], qty, p["price_egp"]))
        fee = shipping_fee(city, subtotal)
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
                    (oid, cid, order_date.isoformat(), status, pick(PAYMENTS), city, fee, subtotal + fee))

    # Gold tier = 100,000 EGP or more in delivered orders over the last 12 months (POL-009).
    con.execute("""
        UPDATE customers SET loyalty_tier = 'gold' WHERE customer_id IN (
            SELECT customer_id FROM orders
            WHERE status = 'delivered' AND order_date >= date(?, '-12 months')
            GROUP BY customer_id HAVING SUM(total_egp) >= 100000)""", (today.isoformat(),))
    con.commit()

    for table in ("customers", "products", "orders", "order_items"):
        print(f"{table:12} {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>4} rows")
    con.close()
    print(f"Saved {DB_PATH}")


if __name__ == "__main__":
    main()
