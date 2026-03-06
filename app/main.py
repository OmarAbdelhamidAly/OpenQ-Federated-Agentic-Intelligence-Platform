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
from app.routers import auth, users, data_sources, analysis, reports, metrics, knowledge, policies

logger = structlog.get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    logger.info("application_starting", log_level=settings.LOG_LEVEL)
    
    # ── Aggressive Self-Healing Database Schema ──
    from sqlalchemy import text
    from app.infrastructure.database.postgres import engine, Base
    # Import all models to ensure they are registered with Base
    from app.models import tenant, user, data_source, analysis_job, analysis_result, knowledge, metric, policy

    logger.info("db_sync_started")
    try:
        # 1. Create all missing tables (safe if they already exist)
        # Wrap in its own try/except to handle race conditions between workers
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("db_tables_synced")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("db_tables_already_exists_skipping")
            else:
                logger.warning("db_tables_sync_warning", error=str(e))

        # 2. Add missing columns and constraints individually
        async def _safe_exec(sql: str):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(sql))
            except Exception as e:
                err_str = str(e).lower()
                if "already exists" not in err_str and "duplicate" not in err_str:
                    logger.warning("db_sync_step_failed", sql=sql[:50], error=str(e))

        # Add columns for SQL Workflow Enhancements
        await _safe_exec("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS generated_sql TEXT NULL")
        await _safe_exec("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS kb_id UUID NULL")
        await _safe_exec("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS thinking_steps JSON NULL")
        
        # Try to add the FK reference safely without Postgres logging errors if it exists
        await _safe_exec("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_analysis_jobs_kb') THEN
                    ALTER TABLE analysis_jobs ADD CONSTRAINT fk_analysis_jobs_kb FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL;
                END IF;
            END $$;
        """)

        # Update status constraint safely
        await _safe_exec("""
            DO $$
            BEGIN
                ALTER TABLE analysis_jobs DROP CONSTRAINT IF EXISTS ck_analysis_jobs_status;
                ALTER TABLE analysis_jobs ADD CONSTRAINT ck_analysis_jobs_status CHECK (status IN ('pending', 'running', 'done', 'error', 'awaiting_approval'));
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END $$;
        """)
        
        logger.info("db_sync_complete")
    except Exception as exc:
        logger.error("db_sync_critical_failure", error=str(exc))

    yield
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""
    _is_prod = settings.ENV == "production"
    app = FastAPI(
        title="Autonomous Data Analyst Agent",
        description="Multi-tenant SaaS platform for AI-powered data analysis.",
        version="1.0.0",
        lifespan=lifespan,
        # Hide API docs in production to reduce attack surface
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
        openapi_url=None if _is_prod else "/openapi.json",
    )

    # Middleware
    setup_middleware(app)

    # Routers
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(data_sources.router)
    app.include_router(analysis.router)
    app.include_router(reports.router)
    app.include_router(metrics.router)
    app.include_router(knowledge.router)
    app.include_router(policies.router)

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

