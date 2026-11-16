"""One place that creates chat models, so the rest of the project does not care which provider is used.

Two providers are supported, chosen by LLM_PROVIDER in .env:

    openrouter   one key, many models (we use DeepSeek). OpenRouter speaks the same API as
                 OpenAI, so we use LangChain's ChatOpenAI and only change the address (base_url).
    gemini       Google's free tier, used in Phases 0 to 5.

Everything else (tools, structured output, the agent) is the same code for both: that is the
point of LangChain's common chat-model interface.
"""
import os

from shopmind.config import LLM_PROVIDER

OPENROUTER_URL = "https://openrouter.ai/api/v1"


def chat_model(name: str, temperature: float | None = 0, max_retries: int = 1, timeout: int = 60):
    if LLM_PROVIDER == "openrouter":
        from langchain_openai import ChatOpenAI
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError("OPENROUTER_API_KEY is empty in .env")
        return ChatOpenAI(model=name, base_url=OPENROUTER_URL, api_key=os.environ["OPENROUTER_API_KEY"],
                          temperature=temperature, max_retries=max_retries, timeout=timeout)
    from langchain.chat_models import init_chat_model
    return init_chat_model(f"google_genai:{name}", temperature=temperature, max_retries=max_retries, timeout=timeout)
