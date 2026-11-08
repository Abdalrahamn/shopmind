"""Sanity checks for Phase 1: is the data where we expect it?

Runs one keyword search, one semantic search and one filtered search against
Weaviate, and one SQL query against shop.db. The search techniques themselves
are the subject of Phase 2; this only proves the index is usable.

Run: python scripts/check_index.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weaviate  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from weaviate.classes.query import Filter  # noqa: E402

from shopmind.config import DB_PATH, EMBEDDING_MODEL, WEAVIATE_COLLECTION  # noqa: E402


def show(title, objects):
    print(f"\n{title}")
    for o in objects:
        p = o.properties
        print(f"  - {p['doc_id']:<13} {p['title'][:40]:<40} | {p['section'][:45]}")


model = SentenceTransformer(EMBEDDING_MODEL)

with weaviate.connect_to_local() as client:
    docs = client.collections.get(WEAVIATE_COLLECTION)

    show("Keyword (BM25): 'Vodafone Cash'", docs.query.bm25("Vodafone Cash", limit=3).objects)

    q = "how many days do I have to send back headphones I already opened?"
    vec = model.encode(q, normalize_embeddings=True).tolist()
    show(f"Semantic: '{q}'", docs.query.near_vector(vec, limit=3).objects)

    q = "phone with a good camera"
    vec = model.encode(q, normalize_embeddings=True).tolist()
    cheap_phones = (Filter.by_property("category").equal("phones")
                    & Filter.by_property("price_egp").less_than(20000))
    show(f"Semantic + filter (phones under 20,000 EGP): '{q}'",
         docs.query.near_vector(vec, limit=3, filters=cheap_phones).objects)

con = sqlite3.connect(DB_PATH)
print("\nSQL: top 3 customers by delivered spend")
rows = con.execute("""
    SELECT c.full_name, c.city, c.loyalty_tier, SUM(o.total_egp) AS spent
    FROM orders o JOIN customers c USING (customer_id)
    WHERE o.status = 'delivered'
    GROUP BY c.customer_id ORDER BY spent DESC LIMIT 3""").fetchall()
for name, city, tier, spent in rows:
    print(f"  - {name:<22} {city:<11} {tier:<8} {spent:>9,} EGP")
