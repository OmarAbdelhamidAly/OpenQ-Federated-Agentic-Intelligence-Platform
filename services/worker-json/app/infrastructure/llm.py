"""Centralized LLM Factory.

All agents should use `get_llm()` instead of instantiating ChatGroq/ChatOpenAI
directly. This makes it easy to swap providers in one place.

Currently configured for **OpenRouter** (OpenAI-compatible API).
"""

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.infrastructure.config import settings


def get_llm(temperature: float = 0, model: str | None = None) -> BaseChatModel:
    """Return a configured LLM instance with strict fallback chain: Groq -> Gemini -> OpenRouter -> Ollama."""
    
    primary_model_name = model or settings.LLM_MODEL
    
    def _make_gemini(m: str = "gemini-1.5-flash"):
        # We use ChatOpenAI because Gemini supports OpenAI protocol, breaking free from old SDK
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=m,
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=temperature,
            max_tokens=4096,
            max_retries=0,
        )

    def _make_openrouter(m: str = "google/gemma-2-9b-it"):
        return ChatOpenAI(
            model=m,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=2048, # Reduce tokens to save context
            max_retries=0, # No internal retries, use LangChain fallbacks instead
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "DataAnalyst.AI",
            },
        )

    def _make_groq(m: str = "llama-3.1-8b-instant"):
        # Use 8B by default to avoid extreme TPM limits of 70B on free tier
        return ChatOpenAI(
            model=m,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
            max_tokens=2048,
            max_retries=0, # No internal retries, use LangChain fallbacks instead
        )

    def _make_ollama(m: str = "llama3.1"):
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError("langchain-ollama is not installed.")
        return ChatOllama(
            model=m,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    # 1. Instantiate Primary Model
    if primary_model_name.startswith("ollama/"):
        m_name = primary_model_name.replace("ollama/", "")
        llm = _make_ollama(m_name)
    elif "gemini" in primary_model_name:
        llm = _make_gemini(primary_model_name)
    elif "groq" in primary_model_name or "llama-3" in primary_model_name:
        m_name = primary_model_name.replace("groq/", "") if primary_model_name.startswith("groq/") else primary_model_name
        llm = _make_groq(m_name)
    else:
        # Default to Groq 8B if not specified
        llm = _make_groq("llama-3.1-8b-instant")

    # 2. Build Direct Fallback Chain (Optimized for speed)
    # Priority: Primary (Gemini) -> Groq 8B
    fallbacks = []

    # If primary isn't Groq, use Groq as the fast fallback
    if settings.GROQ_API_KEY and "groq" not in primary_model_name:
        fallbacks.append(_make_groq("llama-3.1-8b-instant"))

    # If primary isn't Gemini, and we have the key, add it as a backup (though usually Gemini is primary)
    if settings.GEMINI_API_KEY and "gemini" not in primary_model_name:
        fallbacks.append(_make_gemini("gemini-pro"))

    if fallbacks:
        return llm.with_fallbacks(fallbacks)
        
    return llm



