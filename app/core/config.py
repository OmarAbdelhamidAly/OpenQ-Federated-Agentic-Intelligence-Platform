"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every value comes from `.env` or env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Groq API ───────────────────────────────────────────────
    GROCK_API_KEY: str = ""

    # ── AES-256 Encryption ────────────────────────────────────
    AES_KEY: str = "Y2hhbmdlLW1lLXRvLWEtcmFuZG9tLTMyLWJ5dGVz"

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS_ORIGINS JSON string into a list."""
        return json.loads(self.CORS_ORIGINS)


settings = Settings()
