"""Application configuration for worker-code service."""
from __future__ import annotations
import os
import json
from typing import List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Central configuration for worker-code service."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore" # Ignore extra env vars not defined here
    )

    # ── Environment ───────────────────────────────────────────
    ENV: str = "development"

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Neo4j ─────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "analyst_neo4j_password"

    # ── LLM APIs ──────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    LLM_MODEL: str = "google/gemini-flash-1.5-8b"
    LLM_MODEL_CODE: str = "deepseek/deepseek-chat-v3-0324"
    LLM_MODEL_SQL: str = "google/gemini-2.0-flash-001"
    LLM_MODEL_PDF: str = "google/gemini-2.0-flash-lite-001"
    LLM_MODEL_NEXUS: str = "google/gemini-2.0-flash-001"
    LLM_MODEL_FAST: str = "meta-llama/llama-3.2-3b-instruct"
    LLM_MODEL_VISION: str = "meta-llama/llama-3.2-11b-vision-instruct"

    # ── Embedding Models ──────────────────────────────────────────────────────
    EMBED_MODEL_GENERAL: str = "intfloat/multilingual-e5-large" # 1024d — main RAG
    EMBED_MODEL_CODE: str = "starencoder"                       # 768d  — code-specialized
    EMBED_MODEL_CACHE: str = "nomic-ai/nomic-embed-text-v1.5"  # 768d  — local cache
    EMBED_DIM_GENERAL: int = 1024
    EMBED_DIM_CACHE: int = 768

    # ── Qdrant (Semantic Cache) ────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> List[str]:
        """Placeholder for architectural consistency."""
        return []

settings = Settings()
