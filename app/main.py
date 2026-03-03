"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.infrastructure.config import settings
from app.infrastructure.middleware import setup_middleware
from app.routers import auth, users, data_sources, analysis, reports

logger = structlog.get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    logger.info("application_starting", log_level=settings.LOG_LEVEL)
    yield
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""
    app = FastAPI(
        title="Autonomous Data Analyst Agent",
        description="Multi-tenant SaaS platform for AI-powered data analysis.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middleware
    setup_middleware(app)

    # Routers
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(data_sources.router)
    app.include_router(analysis.router)
    app.include_router(reports.router)

    # Serve static assets (CSS, JS, images)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Health check
    @app.get("/health", tags=["health"])
    async def health_check() -> Dict[str, str]:
        """Health check endpoint — returns 200 if the service is up."""
        return {"status": "ok"}

    # Serve frontend SPA at root
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()

