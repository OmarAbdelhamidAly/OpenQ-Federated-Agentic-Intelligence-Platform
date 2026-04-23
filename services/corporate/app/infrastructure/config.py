"""Application configuration for the Corporate service."""

from __future__ import annotations
import json
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Corporate service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────
    ENV: str = "development"

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── JWT Security ──────────────────────────────────────────
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"
    ALGORITHM: str = "HS256"

    # ── AI Models (via OpenRouter) ────────────────────────────
    OPENROUTER_API_KEY: str = ""
    LLM_MODEL_STRATEGIC: str = "google/gemini-pro-1.5"
    LLM_MODEL_FAST: str = "google/gemini-flash-1.5"
    
    # ── Neo4j Knowledge Graph ─────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "analyst_neo4j_password"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> List[str]:
        return ["*"]


settings = Settings()
