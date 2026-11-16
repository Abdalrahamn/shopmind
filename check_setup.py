"""Phase 0 smoke test: checks the LLM (DeepSeek or Gemini), LangSmith config, Weaviate and the embedding model."""
import os
from dotenv import load_dotenv

load_dotenv()

def check(name, fn):
    try:
        print(f"[OK]   {name}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:200]}")

def llm():
    from shopmind.config import CHAT_MODEL, LLM_PROVIDER
    from shopmind.llm import chat_model
    reply = chat_model(CHAT_MODEL).invoke("Say hello in one word").text.strip()
    return f"{LLM_PROVIDER} · {CHAT_MODEL} · {reply}"

def langsmith():
    if not os.getenv("LANGSMITH_API_KEY"):
        raise RuntimeError("LANGSMITH_API_KEY is empty in .env")
    return f"tracing={os.getenv('LANGSMITH_TRACING')} project={os.getenv('LANGSMITH_PROJECT')}"

def weaviate_ready():
    import weaviate
    client = weaviate.connect_to_local()
    try:
        return f"ready={client.is_ready()}"
    finally:
        client.close()

def embeddings():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return f"vector size={len(model.encode('hello'))}"

check("LLM", llm)
check("LangSmith", langsmith)
check("Weaviate", weaviate_ready)
check("Embeddings", embeddings)
