"""Audio Intelligence Worker — Application Configuration."""
from __future__ import annotations
import json
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "change-me-to-a-random-64-char-string"
_DEFAULT_AES_KEY = "Y2hhbmdlLW1lLXRvLWEtcmFuZG9tLTMyLWJ5dGVz"


class Settings(BaseSettings):
    """Central configuration — every value comes from `.env` or env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────────────────────
    ENV: str = "development"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analyst_agent"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"

    # ── LLM APIs ──────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # ── Audio-specific Model Selection ───────────────────────────────────────
    # Stage 1: Transcription + Speaker Diarization (supports Audio Input)
    LLM_MODEL_AUDIO_TRANSCRIBE: str = "google/gemini-2.5-flash-preview"
    # Stage 1 Fallback
    LLM_MODEL_AUDIO_TRANSCRIBE_FALLBACK: str = "google/gemini-2.0-flash-001"
    # Stage 2: Entity Extraction (text only — cheapest)
    LLM_MODEL_AUDIO_ENTITY: str = "meta-llama/llama-3.1-8b-instruct"
    # Stage 3: Summary & Insight Report
    LLM_MODEL_AUDIO_SUMMARY: str = "google/gemini-2.0-flash-lite-001"

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "analyst_neo4j_password"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"

    # ── AES-256 Encryption ────────────────────────────────────────────────────
    AES_KEY: str = _DEFAULT_AES_KEY

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Audio Upload Limits ───────────────────────────────────────────────────
    MAX_AUDIO_SIZE_MB: int = 200  # Max audio file size (200MB = ~3h at 128kbps)
    MAX_AUDIO_DURATION_SECONDS: int = 10800  # 3 hours

    # ── Embedding Models ──────────────────────────────────────────────────────
    EMBED_MODEL_GENERAL: str = "intfloat/multilingual-e5-large" # 1024d — main RAG, multilingual
    EMBED_MODEL_CACHE: str = "nomic-ai/nomic-embed-text-v1.5"  # 768d  — local cache
    EMBED_DIM_GENERAL: int = 1024
    EMBED_DIM_CACHE: int = 768

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.ENV == "production":
            if self.SECRET_KEY == _DEFAULT_SECRET_KEY:
                raise ValueError("[SECURITY] SECRET_KEY must be changed in production!")
            if self.AES_KEY == _DEFAULT_AES_KEY:
                raise ValueError("[SECURITY] AES_KEY must be changed in production!")
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        return json.loads('[\"http://localhost:3000\"]')


settings = Settings()
