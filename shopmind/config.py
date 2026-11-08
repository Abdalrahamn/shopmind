"""Shared settings and paths for ShopMind."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DOCS_DIR = ROOT / "data" / "docs"
DB_PATH = ROOT / "data" / "shop.db"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

WEAVIATE_COLLECTION = "StoreDocs"

# Chunking: sized for MiniLM, which reads at most 256 word pieces (~180 words).
CHUNK_SIZE = 800       # characters
CHUNK_OVERLAP = 120    # characters
