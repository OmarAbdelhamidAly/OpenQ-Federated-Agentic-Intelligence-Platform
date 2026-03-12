"""Centralized LLM Factory.

All agents should use `get_llm()` instead of instantiating ChatGroq/ChatOpenAI
directly. This makes it easy to swap providers in one place.

Currently configured for **OpenRouter** (OpenAI-compatible API).
"""

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.infrastructure.config import settings


def get_llm(temperature: float = 0, model: str | None = None) -> BaseChatModel:
    """Return a configured LLM instance with automatic fallbacks via Gemini, Groq, and OpenRouter."""
    
    primary_model_name = model or settings.LLM_MODEL
    
    def _make_gemini(m: str):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            import langchain_google_genai.chat_models
            
            # Monkey-patch to fix hardcoded Tenacity retries in Langchain Google GenAI
            # This ensures 429 Rate Limits throw instantly so our fallbacks trigger
            def _no_retry_decorator():
                def decorator(fn):
                    return fn
                return decorator
            langchain_google_genai.chat_models._create_retry_decorator = _no_retry_decorator
            
        except ImportError:
            raise ImportError("langchain-google-genai is not installed. Please add it to requirements.txt")
        return ChatGoogleGenerativeAI(
            model=m,
            api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
            max_tokens=4096,
        )

    def _make_openrouter(m: str):
        return ChatOpenAI(
            model=m,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=4096,
            max_retries=0,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "DataAnalyst.AI",
            },
        )

    def _make_groq(m: str):
        return ChatOpenAI(
            model=m,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
            max_tokens=4096,
            max_retries=0,
        )

    def _make_ollama(m: str):
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError("langchain-ollama is not installed. Please add it to requirements.txt")
        return ChatOllama(
            model=m,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    # 1. Determine Primary Model
    if primary_model_name.startswith("ollama/"):
        m_name = primary_model_name.replace("ollama/", "")
        llm = _make_ollama(m_name)
    elif primary_model_name.startswith("gemini") or (settings.GEMINI_API_KEY and not any(x in primary_model_name for x in ["groq", "google/", "ollama/"])):
        # e.g., gemini-1.5-pro
        llm = _make_gemini(primary_model_name)
    elif primary_model_name.startswith("groq/") or (settings.GROQ_API_KEY and not settings.OPENROUTER_API_KEY and not settings.GEMINI_API_KEY):
        m_name = primary_model_name.replace("groq/", "") if primary_model_name.startswith("groq/") else "llama-3.3-70b-versatile"
        llm = _make_groq(m_name)
    else:
        llm = _make_openrouter(primary_model_name)
    
    # 2. Define Fallbacks (always work down the chain: Gemini -> Groq -> OpenRouter)
    fallbacks = []
    
    # If primary isn't Gemini, and we have a Gemini key, use Gemini as the first ultimate fallback
    if settings.GEMINI_API_KEY and not primary_model_name.startswith("gemini"):
        fallbacks.append(_make_gemini("gemini-2.5-pro"))
        fallbacks.append(_make_gemini("gemini-2.5-flash"))

    # If primary isn't Groq, and we have a Groq key, use Groq as the next fallback
    if settings.GROQ_API_KEY and not primary_model_name.startswith("groq/"):
        fallbacks.append(_make_groq("llama-3.3-70b-versatile"))
        fallbacks.append(_make_groq("llama-3.1-8b-instant"))

    # Finally, add OpenRouter free models as the last resort
    if settings.OPENROUTER_API_KEY:
        openrouter_free = [
            "google/gemma-2-9b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]
        for m in openrouter_free:
            if m != primary_model_name:
                fallbacks.append(_make_openrouter(m))

    if fallbacks:
        # Prevent API failure by chaining all fallbacks
        return llm.with_fallbacks(fallbacks)
        
    return llm



