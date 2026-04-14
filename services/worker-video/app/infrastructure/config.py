"""Shared configuration for multimodal workers (Image / Audio / Video)."""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables / .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────
    ENV: str = "development"

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── Redis (Celery) ──────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Neo4j (Knowledge Graph) ─────────────────────────────────
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "analyst_neo4j_password"

    # ── OpenRouter (Primary AI Gateway) ────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    MULTIMODAL_MODEL: str = "google/gemini-flash-1.5"

    # ── Logging ─────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


settings = Settings()
