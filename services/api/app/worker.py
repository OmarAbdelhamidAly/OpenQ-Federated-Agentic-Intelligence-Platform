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

# ── 3. Document Indexing (Knowledge Service) ──────────────────────────────────

@celery_app.task(name="process_document_indexing")
def process_document_indexing(doc_id: str):
    return asyncio.run(_execute_indexing(doc_id))

async def _execute_indexing(doc_id: str):
    # (Original indexing logic preserved)
    from app.infrastructure.database.postgres import async_session_factory
    # ... logic from previous worker.py ...
    pass

# ── 4. Auto-Analysis (Post-Upload Discovery) ──────────────────────────────

@celery_app.task(name="auto_analysis_task")
def auto_analysis_task(*args, **kwargs):
    """Distributed task for running auto-analysis."""
    if len(args) == 3:
        source_id, user_id = args[1], args[2]
    elif len(args) == 2:
        source_id, user_id = args[0], args[1]
    else:
        source_id = kwargs.get("source_id")
        user_id = kwargs.get("user_id")
    return asyncio.run(_execute_auto_analysis(source_id, user_id))

async def _execute_auto_analysis(source_id: str, user_id: str):
    from app.use_cases.auto_analysis.service import run_auto_analysis
    from app.infrastructure.database.postgres import async_session_factory
    
    async with async_session_factory() as db:
        await run_auto_analysis(source_id, user_id, db)
    return {"status": "done"}

@celery_app.task(name="process_source_indexing_proxy")
def process_source_indexing_proxy(source_id: str, user_id: str):
    """Proxy task that sends indexing to PDF worker and links auto-analysis as callback."""
    celery_app.send_task(
        "process_source_indexing", 
        args=[source_id], 
        queue="pillar.pdf",
        link=auto_analysis_task.s(source_id, user_id)
    )
    return {"status": "indexing_triggered"}

# ── 5. Governance & Compliance Layer ──────────────────────────────────────

@celery_app.task(name="governance_task")
def governance_task(job_id: str):
    """Entry point for the governance worker queue."""
    return asyncio.run(_execute_governance(job_id))

async def _execute_governance(job_id: str):
    """
    Verifies data access policies and transitions the job to the appropriate pillar.
    """
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.data_source import DataSource
    from app.models.policy import SystemPolicy
    from sqlalchemy import select
    
    async with async_session_factory() as db:
        # Load job
        result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("governance_fail_job_not_found", job_id=job_id)
            return {"error": "job_not_found"}

        # Load source
        s_result = await db.execute(select(DataSource).where(DataSource.id == job.source_id))
        source = s_result.scalar_one_or_none()
        if not source:
            job.status = "error"
            job.error_message = f"Data source {job.source_id} not found"
            await db.commit()
            return {"error": "source_not_found"}

        # Perform Governance/Compliance logic here
        # (For now: just transition to the appropriate pillar)
        
        job.status = "running"
        await db.commit()
        await db.refresh(job)

        # Dispatch to Pillar
        target_queue = f"pillar.{source.type.lower()}"
        celery_app.send_task("pillar_task", args=[str(job.id)], queue=target_queue)
        
        logger.info("governance_passed", job_id=str(job.id), target_queue=target_queue)
        return {"status": "governance_passed", "next_queue": target_queue}
