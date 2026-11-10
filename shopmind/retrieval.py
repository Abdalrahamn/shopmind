"""Phase 2: every retrieval method in one place.

Methods (all return a list of Hit, best first):
    tfidf          TF-IDF written from scratch (keyword_search.py)
    bm25_scratch   BM25 written from scratch (keyword_search.py)
    bm25           Weaviate's built-in BM25 (keyword search)
    semantic       vector search with sentence-transformers embeddings
    hybrid         BM25 + semantic merged with Reciprocal Rank Fusion (our own code)
    weaviate_hybrid  Weaviate's built-in hybrid search, for comparison

Extras that work with any method:
    filters        metadata filtering (type, category, brand, price, archived)
    rerank         re-score the candidates with a cross-encoder
    rewrite        let Gemini rewrite the question and extract filters first
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import weaviate
from sentence_transformers import CrossEncoder, SentenceTransformer
from weaviate.classes.query import Filter, HybridFusion, MetadataQuery

from shopmind.config import EMBEDDING_MODEL, WEAVIATE_COLLECTION
from shopmind.keyword_search import BM25Index, TfidfIndex

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
METHODS = ["tfidf", "bm25_scratch", "bm25", "semantic", "hybrid", "weaviate_hybrid"]

# The setup chosen from the Phase 2 evaluation (see reports/retrieval_findings.md).
DEFAULT_SEARCH = dict(method="hybrid", rewrite=True, rerank=False)


@dataclass
class SearchFilters:
    """Metadata filters. Archived documents are hidden unless asked for."""
    doc_type: str | None = None          # policy | faq | product
    category: str | None = None          # e.g. returns, phones, laptops
    brand: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    include_archived: bool = False

    def to_weaviate(self):
        parts = []
        if not self.include_archived:
            parts.append(Filter.by_property("status").equal("active"))
        if self.doc_type:
            parts.append(Filter.by_property("doc_type").equal(self.doc_type))
        if self.category:
            parts.append(Filter.by_property("category").equal(self.category))
        if self.brand:
            parts.append(Filter.by_property("brand").equal(self.brand))
        if self.min_price is not None:
            parts.append(Filter.by_property("price_egp").greater_or_equal(self.min_price))
        if self.max_price is not None:
            parts.append(Filter.by_property("price_egp").less_or_equal(self.max_price))
        return Filter.all_of(parts) if parts else None

    def matches(self, p: dict) -> bool:
        """Same rules as to_weaviate, for the from-scratch indexes that run in Python."""
        price = p.get("price_egp")
        return ((self.include_archived or p["status"] == "active")
                and (not self.doc_type or p["doc_type"] == self.doc_type)
                and (not self.category or p["category"] == self.category)
                and (not self.brand or (p.get("brand") or "").lower() == self.brand.lower())
                and (self.min_price is None or (price is not None and price >= self.min_price))
                and (self.max_price is None or (price is not None and price <= self.max_price)))


@dataclass
class Hit:
    id: str
    score: float
    properties: dict
    method: str
    extra: dict = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return self.properties["doc_id"]

    @property
    def text(self) -> str:
        return self.properties["text"]


class Retriever:
    def __init__(self):
        self.client = weaviate.connect_to_local()
        self.collection = self.client.collections.get(WEAVIATE_COLLECTION)
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        self._reranker = None
        self._rewriter = None
        self._rewrites = {}  # cache: the same question is only sent to Gemini once

        # The from-scratch indexes need every chunk in memory (88 chunks, tiny).
        self.chunks = [(str(o.uuid), o.properties) for o in self.collection.iterator()]
        texts = [p["text"] for _, p in self.chunks]
        self.tfidf_index = TfidfIndex(texts)
        self.bm25_index = BM25Index(texts)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ methods
    def _from_scratch(self, scores, k, filters, method) -> list[Hit]:
        order = scores.argsort()[::-1]
        hits = []
        for i in order:
            if scores[i] <= 0:
                break
            uid, props = self.chunks[i]
            if filters.matches(props):
                hits.append(Hit(uid, float(scores[i]), props, method))
            if len(hits) == k:
                break
        return hits

    def tfidf(self, query, k=5, filters=None):
        return self._from_scratch(self.tfidf_index.scores(query), k, filters or SearchFilters(), "tfidf")

    def bm25_scratch(self, query, k=5, filters=None):
        return self._from_scratch(self.bm25_index.scores(query), k, filters or SearchFilters(), "bm25_scratch")

    def bm25(self, query, k=5, filters=None):
        res = self.collection.query.bm25(query, limit=k, filters=(filters or SearchFilters()).to_weaviate(),
                                         return_metadata=MetadataQuery(score=True))
        return [Hit(str(o.uuid), o.metadata.score, o.properties, "bm25") for o in res.objects]

    def embed(self, text: str) -> list[float]:
        return self.embedder.encode(text, normalize_embeddings=True).tolist()

    def semantic(self, query, k=5, filters=None):
        res = self.collection.query.near_vector(self.embed(query), limit=k,
                                                filters=(filters or SearchFilters()).to_weaviate(),
                                                return_metadata=MetadataQuery(distance=True))
        return [Hit(str(o.uuid), 1 - o.metadata.distance, o.properties, "semantic") for o in res.objects]

    def hybrid(self, query, k=5, filters=None, candidates=20, rrf_k=60):
        """Reciprocal Rank Fusion: score = sum of 1 / (rrf_k + rank) over both result lists.

        RRF only looks at ranks, not raw scores, so it does not matter that
        BM25 scores (0 to ~10) and cosine similarities (0 to 1) are on
        different scales. A chunk that is high in both lists wins.
        """
        lists = {"bm25": self.bm25(query, candidates, filters), "semantic": self.semantic(query, candidates, filters)}
        fused: dict[str, Hit] = {}
        for name, hits in lists.items():
            for rank, h in enumerate(hits, 1):
                if h.id not in fused:
                    fused[h.id] = Hit(h.id, 0.0, h.properties, "hybrid", {})
                fused[h.id].score += 1 / (rrf_k + rank)
                fused[h.id].extra[f"{name}_rank"] = rank
        return sorted(fused.values(), key=lambda h: h.score, reverse=True)[:k]

    def weaviate_hybrid(self, query, k=5, filters=None, alpha=0.5):
        res = self.collection.query.hybrid(query, vector=self.embed(query), alpha=alpha, limit=k,
                                           fusion_type=HybridFusion.RANKED,
                                           filters=(filters or SearchFilters()).to_weaviate(),
                                           return_metadata=MetadataQuery(score=True))
        return [Hit(str(o.uuid), o.metadata.score, o.properties, "weaviate_hybrid") for o in res.objects]

    # ------------------------------------------------------------ extras
    def rerank(self, query: str, hits: list[Hit], k: int) -> list[Hit]:
        """A cross-encoder reads the question and each chunk together and scores
        how well the chunk answers it. Slower than embeddings (one model call per
        chunk), so we only use it on a short list of candidates."""
        if not hits:
            return hits
        if self._reranker is None:
            self._reranker = CrossEncoder(RERANK_MODEL)
        scores = self._reranker.predict([(query, h.text) for h in hits])
        reranked = [replace(h, score=float(s), extra={**h.extra, "before_rerank": i})
                    for i, (h, s) in enumerate(zip(hits, scores), 1)]
        return sorted(reranked, key=lambda h: h.score, reverse=True)[:k]

    def rewrite(self, question: str):
        if self._rewriter is None:
            from shopmind.query_rewriter import QueryRewriter
            self._rewriter = QueryRewriter()
        if question not in self._rewrites:
            self._rewrites[question] = self._rewriter.rewrite(question)
        return self._rewrites[question]

    def search(self, query: str, method: str = "hybrid", k: int = 5, filters: SearchFilters | None = None,
               rerank: bool = False, rewrite: bool = False, unique_docs: bool = False) -> list[Hit]:
        """The one entry point used by the app and the evaluation.

        unique_docs keeps only the best chunk of each document, so the top k are
        k different documents (that is how we measure Precision@K and Recall@K).
        """
        filters = filters or SearchFilters()
        plan = None
        if rewrite:
            plan = self.rewrite(query)
            query = plan.query
            filters = plan.merge_into(filters)

        fetch = k * 4 if (rerank or unique_docs) else k
        hits = getattr(self, method)(query, fetch, filters)
        if rerank:
            hits = self.rerank(query, hits, len(hits))
        if unique_docs:
            seen, deduped = set(), []
            for h in hits:
                if h.doc_id not in seen:
                    seen.add(h.doc_id)
                    deduped.append(h)
            hits = deduped
        hits = hits[:k]
        if plan is not None:
            for h in hits:
                h.extra["rewritten_query"] = query
        return hits
