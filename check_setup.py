"""Phase 0 smoke test: checks Gemini, LangSmith config, and Weaviate."""
import os
from dotenv import load_dotenv

load_dotenv()

def check(name, fn):
    try:
        print(f"[OK]   {name}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:200]}")

def gemini():
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is empty in .env")
    from langchain.chat_models import init_chat_model
    llm = init_chat_model("google_genai:gemini-2.5-flash")
    return llm.invoke("Say hello in one word").content

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

check("Gemini", gemini)
check("LangSmith", langsmith)
check("Weaviate", weaviate_ready)
check("Embeddings", embeddings)
