"""Query rewriting with Gemini.

Customers write short, messy or Arabic questions ("عايز موبايل كويس تحت 15 الف").
Our embedding model only knows English and the documents use store words
("return window", "instalments"). Gemini turns the question into:
  - a clean English search query that uses the store's vocabulary, and
  - metadata filters it can read from the question (type, category, price...).

It uses structured output (a Pydantic model), so the answer is always valid data.
"""
from __future__ import annotations

import json
from typing import Literal

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from shopmind.config import CACHE_DIR, REWRITE_FALLBACKS, REWRITE_MODEL

CATEGORIES = Literal["returns", "shipping", "warranty", "payment", "orders", "pricing", "privacy", "loyalty",
                     "products", "store", "phones", "laptops", "audio", "accessories", "smart-home", "gaming"]

PROMPT = """You turn a customer's question into a search request for an Egyptian electronics store's knowledge base.

The knowledge base has policies (returns, shipping, warranty, payment, instalments, cancellation, price match,
privacy, loyalty points), FAQs, and product pages (phones, laptops, audio, accessories, smart-home, gaming)
with prices in EGP.

Rules:
- Write `query` in English, even if the question is in Arabic. Keep the customer's meaning; add the words
  a store policy or product page would use (for example "return window", "refund", "instalments",
  "shipping fee"). Keep it short: one line, no explanations.
- Only fill a filter when the question clearly asks for it. Leave it empty when unsure: a wrong filter
  hides the right answer.
- Prices: "under 15k" or "تحت 15 الف" means max_price 15000.
- Set include_archived only if the customer asks about an old or previous policy.

Question: {question}"""


class SearchPlan(BaseModel):
    query: str = Field(description="Clean English search query using store vocabulary")
    doc_type: Literal["policy", "faq", "product"] | None = None
    category: CATEGORIES | None = None
    brand: str | None = Field(None, description="Brand name exactly as written, e.g. Samsung, Apple")
    min_price: float | None = None
    max_price: float | None = None
    include_archived: bool = False

    def merge_into(self, filters):
        """Turn the plan into hard filters, carefully.

        Only constraints the customer actually stated become filters: a price
        limit, or asking about an old policy. doc_type, category and brand are
        Gemini's guesses, and the evaluation showed they hide the answer too
        often (an FAQ filtered out as "policy", or "policy + brand Apple", which
        matches nothing because policies have no brand). They stay in the plan
        as hints; the rewritten query already carries those words.
        Filters set by the caller always win.
        """
        from dataclasses import replace
        updates = {}
        for name in ("min_price", "max_price"):
            if getattr(filters, name) is None and getattr(self, name) is not None:
                updates[name] = getattr(self, name)
        if self.include_archived:
            updates["include_archived"] = True
        return replace(filters, **updates)


class QueryRewriter:
    """Rewrites are saved to data/cache/rewrites.json. The free Gemini tier allows
    about 20 requests per model per day, so:
      - the same question is never sent twice (disk cache), and
      - if one model hits its limit, the next model in REWRITE_FALLBACKS answers
        (LangChain's with_fallbacks)."""

    def __init__(self, models: list[str] | None = None):
        models = models or [REWRITE_MODEL, *REWRITE_FALLBACKS]
        chains = [init_chat_model(f"google_genai:{m}", temperature=0, max_retries=0, timeout=30)
                  .with_structured_output(SearchPlan) for m in models]
        self.chain = chains[0].with_fallbacks(chains[1:])
        self.cache_file = CACHE_DIR / "rewrites.json"
        self.cache = json.loads(self.cache_file.read_text(encoding="utf-8")) if self.cache_file.exists() else {}

    def rewrite(self, question: str) -> SearchPlan:
        if question not in self.cache:
            plan = self.chain.invoke(PROMPT.format(question=question))
            self.cache[question] = plan.model_dump()
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        return SearchPlan(**self.cache[question])
