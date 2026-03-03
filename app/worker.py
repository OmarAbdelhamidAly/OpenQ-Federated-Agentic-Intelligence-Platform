"""Celery worker — processes analysis jobs asynchronously."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from celery import Celery

from app.infrastructure.config import settings

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


@celery_app.task(bind=True, name="run_analysis_pipeline", max_retries=3)
def run_analysis_pipeline(self, job_id: str) -> dict:
    """Execute the LangGraph analysis pipeline for a given job.

    This task is dispatched by the analysis router when a user submits
    a query. It runs asynchronously in the Celery worker.
    """
    # Run the async pipeline in a sync context
    return asyncio.run(_execute_pipeline(job_id))


async def _execute_pipeline(job_id: str) -> dict:
    """Internal async execution of the analysis pipeline."""
    from sqlalchemy import select

    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    from app.models.data_source import DataSource
    from app.use_cases.analysis.run_pipeline import get_pipeline

    async with async_session_factory() as db:
        # Load the job
        result = await db.execute(
            select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()
        if job is None:
            return {"error": f"Job {job_id} not found"}

        # Update status
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Load data source
        ds_result = await db.execute(
            select(DataSource).where(DataSource.id == job.source_id)
        )
        source = ds_result.scalar_one_or_none()
        if source is None:
            job.status = "error"
            job.error_message = "Data source not found"
            await db.commit()
            return {"error": "Data source not found"}

        # Build initial state
        initial_state = {
            "tenant_id": str(job.tenant_id),
            "user_id": str(job.user_id),
            "question": job.question,
            "source_id": str(job.source_id),
            "source_type": source.type,
            "file_path": source.file_path,
            "config_encrypted": source.config_encrypted,
            "schema_summary": source.schema_json or {},
            "retry_count": 0,
        }

        try:
            # Run the correct pipeline (CSV or SQL) based on source type
            pipeline = get_pipeline(source.type)
            final_state = await pipeline.ainvoke(initial_state)

            # Save results
            analysis_result = AnalysisResult(
                job_id=job.id,
                chart_json=final_state.get("chart_json"),
                insight_report=final_state.get("insight_report"),
                exec_summary=final_state.get("executive_summary"),
                recommendations_json=final_state.get("recommendations"),
                follow_up_suggestions=final_state.get("follow_up_suggestions"),
            )
            db.add(analysis_result)

            job.status = "done"
            job.intent = final_state.get("intent")
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            return {"status": "done", "job_id": job_id}

        except Exception as e:
            job.status = "error"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"error": str(e), "job_id": job_id}
        finally:
            # CRITICAL: Dispose of the engine to clear the connection pool.
            # This prevents loop-affinity issues when Celery runs the next task
            # on a new event loop (via asyncio.run).
            from app.infrastructure.database.postgres import engine
            await engine.dispose()
