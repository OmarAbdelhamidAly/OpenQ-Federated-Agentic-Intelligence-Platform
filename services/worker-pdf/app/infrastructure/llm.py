"""Centralized LLM Factory.

All agents should use `get_llm()` instead of instantiating ChatGroq/ChatOpenAI
directly. This makes it easy to swap providers in one place.
"""

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.infrastructure.config import settings


def get_llm(temperature: float = 0, model: str | None = None) -> BaseChatModel:
    """Return a configured LLM instance with strict fallback chain."""
    
    # If no model provided, use environment default or hardcoded safe bet
    primary_model_name = model or settings.LLM_MODEL
    
    def _make_gemini(m: str = "gemini-1.5-flash"):
        return ChatOpenAI(
            model=m,
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=temperature,
            max_tokens=4096,
            max_retries=1,
        )

    def _make_groq(m: str = "llama-3.1-8b-instant"):
        return ChatOpenAI(
            model=m,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
            max_tokens=2048,
            max_retries=1,
        )

    # 1. Instantiate Primary Model
    if "gemini" in primary_model_name.lower():
        llm = _make_gemini(primary_model_name)
    elif "groq" in primary_model_name.lower() or "llama-3" in primary_model_name.lower():
        llm = _make_groq(primary_model_name)
    else:
        llm = _make_groq("llama-3.1-8b-instant")

    # 2. Build Fallbacks
    fallbacks = []
    if settings.GEMINI_API_KEY and "gemini" not in primary_model_name.lower():
        fallbacks.append(_make_gemini("gemini-1.5-flash"))
    
    if fallbacks:
        return llm.with_fallbacks(fallbacks)
        
    return llm
