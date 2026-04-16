"""FastAPI application entry point for the Corporate Service."""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("corporate_service_starting", env=settings.ENV)
    
    # ── Database Sync ──
    from sqlalchemy import text
    from app.infrastructure.database import engine, Base
    from app.models import org_node, task, submission

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("db_tables_synced")
    except Exception as e:
        logger.error("db_sync_failed", error=str(e))

    yield
    logger.info("corporate_service_shutting_down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Insightify Corporate Environment Service",
        description="Manages organizational hierarchies, task flows, and company-wide governance.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Instrument Prometheus
    Instrumentator().instrument(app).expose(app)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "corporate"}

    # Placeholder for routers
    # app.include_router(hierarchy.router)
    # app.include_router(tasks.router)

    return app


app = create_app()
