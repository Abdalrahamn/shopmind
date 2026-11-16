"""Shared settings and paths for ShopMind."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DOCS_DIR = ROOT / "data" / "docs"
DB_PATH = ROOT / "data" / "shop.db"

# Which LLM provider answers: "openrouter" (DeepSeek, paid per token, no daily limit) or "gemini" (free tier).
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or ("openrouter" if os.getenv("OPENROUTER_API_KEY") else "gemini")

if LLM_PROVIDER == "openrouter":
    # DeepSeek's newest small model: cheap, supports tools and structured output.
    CHAT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
    REWRITE_MODEL = os.getenv("OPENROUTER_REWRITE_MODEL", "deepseek/deepseek-v4-flash")  # helper tasks: the cheapest
    REWRITE_FALLBACKS = [CHAT_MODEL]
    AGENT_FALLBACKS = ["deepseek/deepseek-v4-flash"]    # tried when the main model fails
else:
    CHAT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    # Small helper tasks (query rewriting) use the lite model: higher free-tier daily quota.
    REWRITE_MODEL = os.getenv("REWRITE_MODEL", "gemini-3.5-flash-lite")
    # Free-tier notes (found the hard way): each model allows about 20 requests per day;
    # "gemini-3.5-flash" and "gemini-3.6-flash" share one quota; 3.7 and 3.8 often hang on the free tier.
    REWRITE_FALLBACKS = ["gemini-3.1-flash-lite"]  # used when the main one hits its limit
    AGENT_FALLBACKS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

GEMINI_MODEL = CHAT_MODEL  # old name, kept so earlier scripts keep working
CACHE_DIR = ROOT / "data" / "cache"
# The agent tries AGENT_MODEL first, then each fallback.
AGENT_MODEL = os.getenv("AGENT_MODEL", CHAT_MODEL)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

WEAVIATE_COLLECTION = "StoreDocs"

# Chunking: sized for MiniLM, which reads at most 256 word pieces (~180 words).
CHUNK_SIZE = 800       # characters
CHUNK_OVERLAP = 120    # characters
