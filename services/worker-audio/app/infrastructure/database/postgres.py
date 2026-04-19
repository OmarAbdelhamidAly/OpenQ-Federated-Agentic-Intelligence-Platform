"""Async SQLAlchemy engine, session factory, and base model."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.infrastructure.config import settings

from sqlalchemy.pool import NullPool

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
    poolclass=NullPool,  # Critical for Celery asyncio.run to avoid "Event loop is closed"
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
    """FastAPI dependency — yields a DB session.

    NOTE: tenant_id is set via `set_tenant_context()` in the
    dependencies layer after the user is authenticated.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set the tenant context for PostgreSQL Row-Level Security.

    Called at the start of every authenticated request.
    Silently skips on non-PostgreSQL databases (e.g. SQLite in tests).
    """
    try:
        await session.execute(
            text(f"SET LOCAL app.tenant_id = '{tenant_id}'")
        )
    except Exception:
        # SQLite and other databases don't support SET LOCAL — skip gracefully
        pass
