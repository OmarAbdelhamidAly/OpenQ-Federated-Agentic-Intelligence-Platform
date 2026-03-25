"""Celery worker — specialized Microservices Architecture."""

from __future__ import annotations
import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from celery import Celery
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "analyst_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# ── 1. Export Generation Task ──────────────────────────────────────────────

@celery_app.task(bind=True, name="generate_export_task", max_retries=3)
def generate_export_task(self, job_id: str, export_format: str) -> dict:
    """Asynchronously generates analysis reports (PDF, CSV, PNG)."""
    return asyncio.run(_execute_export(job_id, export_format))

async def _execute_export(job_id: str, export_format: str) -> dict:
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    from app.use_cases.export.service import ExportService
    
    # Bind context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(job_id=job_id, format=export_format)

    try:
        async with async_session_factory() as db:
            # Fetch Job and Results
            res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
            job = res.scalar_one_or_none()
            if not job: return {"error": "Job not found"}

            result_res = await db.execute(select(AnalysisResult).where(AnalysisResult.job_id == job.id))
            result = result_res.scalar_one_or_none()
            if not result: return {"error": "Analysis results not found"}

            logger.info("export_generation_started")

            # Initialize Export Service
            service = ExportService()
            
            # Generate file based on format
            file_path = None
            if export_format == "pdf":
                file_path = await service.generate_pdf(job, result)
            elif export_format == "csv":
                # Note: CSV usually needs raw data, which is stored in result.chart_json for small sets
                file_path = await service.generate_csv(job, result)
            elif export_format == "png":
                file_path = await service.generate_png(job, result)
            else:
                 return {"error": f"Unsupported format: {export_format}"}

            logger.info("export_generation_complete", path=file_path)
            return {"status": "success", "file_path": file_path}

    except Exception as e:
        logger.error("export_generation_failed", error=str(e))
        return {"error": str(e)}
    finally:
        try:
            from app.infrastructure.database.postgres import engine
            await engine.dispose()
        except Exception:
            pass

# Specialized Exporter Worker
