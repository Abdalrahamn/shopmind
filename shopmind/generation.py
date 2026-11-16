"""Phase 3: answer a question from the retrieved chunks, with citations.

Flow:  question -> retrieve chunks (Phase 2 default) -> prompt Gemini with the
chunks as numbered sources -> structured answer (text, citations, answerable).

Three rules keep the answer honest:
  1. Grounding: the prompt allows only facts found in the sources.
  2. "I don't know": if the sources do not hold the answer, the model must say
     so (answerable = False) instead of guessing.
  3. Citation check: any cited document that was not actually retrieved is
     removed in code, so a made-up citation can never reach the customer.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

from shopmind.llm import chat_model
from pydantic import BaseModel, Field

from shopmind.config import CACHE_DIR, GEMINI_MODEL
from shopmind.retrieval import DEFAULT_SEARCH, Hit, Retriever

PROMPT = """You are ShopMind, the customer assistant of ShopMind Electronics, an online electronics store in Egypt.

Answer the customer's question using ONLY the sources below.

Rules:
- Every fact (days, prices, fees, conditions) must come from the sources. Never use outside knowledge and never guess.
- After each fact, cite the source id in square brackets, for example [POL-001]. List the same ids in `citations`.
- If the sources do not contain the answer, set `answerable` to false, say briefly that you do not have this
  information, and suggest contacting support on 19555. Do not answer from a similar product or a similar policy.
- If only part of the question is covered, answer that part and say clearly what you could not find.
- Reply in the customer's language (Egyptian Arabic if they wrote in Arabic). Keep it short and friendly.

Sources:
{sources}

Customer question: {question}"""


class GroundedAnswer(BaseModel):
    answerable: bool = Field(description="True only if the sources contain the answer")
    answer: str = Field(description="The reply to the customer, with [doc_id] citations after facts")
    citations: list[str] = Field(default_factory=list, description="Ids of the sources used, e.g. POL-001")


@dataclass
class Result:
    question: str
    answer: str
    answerable: bool
    citations: list[str]
    dropped_citations: list[str]          # cited by the model but not in the sources
    source_ids: list[str]                 # documents that were shown to the model
    model: str
    temperature: float
    latency_s: float
    input_tokens: int
    output_tokens: int
    cached: bool = False
    hits: list[Hit] = field(default_factory=list, repr=False)


def format_sources(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{h.doc_id}] {h.properties['title']}\n{h.text}" for h in hits)


class Generator:
    def __init__(self, retriever: Retriever, model: str = GEMINI_MODEL, temperature: float = 0.0):
        self.retriever = retriever
        self.model = model
        self.temperature = temperature
        llm = chat_model(model, temperature=temperature)
        # include_raw gives us the raw message too, which carries the token counts.
        self.chain = llm.with_structured_output(GroundedAnswer, include_raw=True)
        self.cache_file = CACHE_DIR / "answers.json"
        self.cache = json.loads(self.cache_file.read_text(encoding="utf-8")) if self.cache_file.exists() else {}

    def retrieve(self, question: str, k: int = 6) -> list[Hit]:
        try:
            return self.retriever.search(question, k=k, **DEFAULT_SEARCH)
        except Exception:
            # Rewriting needs Gemini; if its quota is out, search with the raw question.
            return self.retriever.search(question, k=k, method=DEFAULT_SEARCH["method"])

    def answer(self, question: str, k: int = 6, run: int = 0, use_cache: bool = True) -> Result:
        """`run` only separates repeated calls in the cache (used by the temperature test)."""
        hits = self.retrieve(question, k)
        source_ids = list(dict.fromkeys(h.doc_id for h in hits))
        key = f"{self.model}|{self.temperature}|{run}|{question}"

        if use_cache and key in self.cache:
            return Result(**self.cache[key], cached=True, hits=hits)

        start = time.perf_counter()
        out = self.chain.invoke(PROMPT.format(sources=format_sources(hits), question=question))
        latency = time.perf_counter() - start
        parsed: GroundedAnswer = out["parsed"]
        if parsed is None:
            raise ValueError(f"Model returned no valid structured answer: {out.get('parsing_error')}")
        usage = getattr(out["raw"], "usage_metadata", None) or {}

        kept = [c for c in dict.fromkeys(parsed.citations) if c in source_ids]
        dropped = [c for c in dict.fromkeys(parsed.citations) if c not in source_ids]
        result = Result(question=question, answer=parsed.answer, answerable=parsed.answerable,
                        citations=kept, dropped_citations=dropped, source_ids=source_ids,
                        model=self.model, temperature=self.temperature, latency_s=round(latency, 2),
                        input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0))

        saved = asdict(result)
        saved.pop("hits"), saved.pop("cached")
        self.cache[key] = saved
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        result.hits = hits
        return result
