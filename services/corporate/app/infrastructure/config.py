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

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> List[str]:
        return ["*"] # Default for now, can be restricted later


settings = Settings()
