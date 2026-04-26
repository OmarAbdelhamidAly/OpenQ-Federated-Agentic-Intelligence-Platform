"""Centralized LLM Factory - STRICT OPENROUTER MODE.
"""
import structlog
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

def get_llm(temperature: float = 0, model: Optional[str] = None) -> BaseChatModel:
    """Return an LLM instance, EXCLUSIVELY using OpenRouter."""
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("CRITICAL: OPENROUTER_API_KEY is missing. System must use OpenRouter.")

    # Model resolution: if agent passes `model` (e.g. from settings.LLM_MODEL_FAST), use it.
    final_model = model or settings.LLM_MODEL or "google/gemini-2.0-flash-001"

    # Enforce basic sane fallback structure if they accidentally passed an ancient groq name
    if "llama-3" in final_model.lower() and "instant" in final_model.lower():
        final_model = settings.LLM_MODEL_FAST  # Automatically upgrade legacy Groq strings

    llm = ChatOpenAI(
        model=final_model,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=4096,
        max_retries=3,
        default_headers={
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_APP_TITLE,
        },
    )

    return llm
