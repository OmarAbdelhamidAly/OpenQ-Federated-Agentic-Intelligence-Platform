"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinel defaults — intentionally weak so the validator catches them in prod
_DEFAULT_SECRET_KEY = "change-me-to-a-random-64-char-string"
_DEFAULT_AES_KEY = "Y2hhbmdlLW1lLXRvLWEtcmFuZG9tLTMyLWJ5dGVz"


class Settings(BaseSettings):
    """Central configuration — every value comes from `.env` or env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Environment ───────────────────────────────────────────
    ENV: str = "development"  # Set to "production" in prod deployments

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ───────────────────────────────────────────────────
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM APIs ──────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "groq/llama-3.1-8b-instant"  # Default fallback, override via .env







    # ── AES-256 Encryption ────────────────────────────────────
    AES_KEY: str = _DEFAULT_AES_KEY

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Upload Limits ─────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 500

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Crash on startup if weak default secrets are used in production."""
        if self.ENV == "production":
            if self.SECRET_KEY == _DEFAULT_SECRET_KEY:
                raise ValueError(
                    "[SECURITY] SECRET_KEY must be changed from the default value in production! "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.AES_KEY == _DEFAULT_AES_KEY:
                raise ValueError(
                    "[SECURITY] AES_KEY must be changed from the default value in production! "
                    "Generate one with: python -c \"import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
                )
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS_ORIGINS JSON string into a list."""
        return json.loads(self.CORS_ORIGINS)


settings = Settings()
