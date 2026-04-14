"""Async SQLAlchemy engine, session factory, and base model — Image Worker."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.infrastructure.config import settings


def json_serial(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=json_serial)


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # Critical for Celery asyncio.run() to avoid "Event loop is closed"
    json_serializer=dumps,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
