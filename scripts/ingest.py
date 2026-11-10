"""Load the store documents, chunk them, embed the chunks and store them in Weaviate.

The collection is deleted and rebuilt on every run, so running it twice never
creates duplicates.

Run: python scripts/ingest.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weaviate  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from weaviate.classes.config import Configure, DataType, Property, Tokenization  # noqa: E402

from shopmind.config import DOCS_DIR, EMBEDDING_MODEL, WEAVIATE_COLLECTION  # noqa: E402
from shopmind.documents import chunk_documents, load_documents  # noqa: E402
from shopmind.keyword_search import STOPWORDS  # noqa: E402

# Filterable labels use FIELD tokenization so "returns" matches exactly and is not split into words.
KEYWORD = dict(data_type=DataType.TEXT, tokenization=Tokenization.FIELD, skip_vectorization=True)

PROPERTIES = [
    Property(name="text", data_type=DataType.TEXT),          # the chunk itself, searched by BM25
    Property(name="title", data_type=DataType.TEXT),
    Property(name="section", data_type=DataType.TEXT),
    Property(name="doc_id", **KEYWORD),
    Property(name="doc_type", **KEYWORD),                     # policy | faq | product
    Property(name="category", **KEYWORD),
    Property(name="status", **KEYWORD),                       # active | archived
    Property(name="source", **KEYWORD),
    Property(name="brand", **KEYWORD),
    Property(name="sku", **KEYWORD),
    Property(name="updated_at", data_type=DataType.DATE),
    Property(name="chunk_index", data_type=DataType.INT),
    Property(name="price_egp", data_type=DataType.NUMBER),
    Property(name="warranty_months", data_type=DataType.INT),
    Property(name="clearance", data_type=DataType.BOOL),
]


def to_properties(meta: dict, text: str) -> dict:
    props = {
        "text": text,
        "title": meta["title"],
        "section": meta.get("section", ""),
        "doc_id": meta["doc_id"],
        "doc_type": meta["doc_type"],
        "category": meta["category"],
        "status": meta["status"],
        "source": meta["source"],
        "updated_at": f"{meta['updated_at']}T00:00:00Z",
        "chunk_index": meta["chunk_index"],
    }
    if meta["doc_type"] == "product":
        props |= {k: meta[k] for k in ("brand", "sku", "price_egp", "warranty_months", "clearance")}
    return props


def main() -> None:
    docs = load_documents(DOCS_DIR)
    chunks = chunk_documents(docs)
    print(f"Loaded {len(docs)} documents -> {len(chunks)} chunks")
    print("  by type:", dict(Counter(c.metadata["doc_type"] for c in chunks)))
    lengths = sorted(len(c.page_content) for c in chunks)
    print(f"  chunk length (chars): min {lengths[0]}, median {lengths[len(lengths) // 2]}, max {lengths[-1]}")

    print(f"Embedding with {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    vectors = model.encode([c.page_content for c in chunks], normalize_embeddings=True,
                           batch_size=32, show_progress_bar=False)
    print(f"  {len(vectors)} vectors of size {vectors.shape[1]}")

    with weaviate.connect_to_local() as client:
        if client.collections.exists(WEAVIATE_COLLECTION):
            client.collections.delete(WEAVIATE_COLLECTION)
        collection = client.collections.create(
            WEAVIATE_COLLECTION,
            vector_config=Configure.Vectors.self_provided(),  # we bring our own embeddings
            # Weaviate's default English stopword list misses words like "how", "can", "i", "do".
            # Without them, BM25 matched FAQ titles such as "How do I ..." instead of the key word.
            inverted_index_config=Configure.inverted_index(stopwords_additions=sorted(STOPWORDS)),
            properties=PROPERTIES,
        )
        with collection.batch.fixed_size(batch_size=100) as batch:
            for chunk, vector in zip(chunks, vectors):
                batch.add_object(properties=to_properties(chunk.metadata, chunk.page_content),
                                 vector=vector.tolist())
        failed = collection.batch.failed_objects
        if failed:
            print(f"  {len(failed)} objects failed, first error: {failed[0].message}")
        total = collection.aggregate.over_all(total_count=True).total_count
        print(f"Stored {total} chunks in Weaviate collection '{WEAVIATE_COLLECTION}'")


if __name__ == "__main__":
    main()
