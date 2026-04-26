"""Celery worker for Universal Strategic Nexus."""
import asyncio
from celery import Celery
import structlog
from app.infrastructure.config import settings
from app.infrastructure.neo4j_adapter import bootstrap_neo4j, Neo4jAdapter

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "worker-nexus",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_queues={
        "pillar.nexus": {"exchange": "pillar.nexus", "routing_key": "pillar.nexus"},
    },
)

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Bootstrap Neo4j once on start."""
    try:
        bootstrap_neo4j()
        logger.info("nexus_worker_bootstrapped")
    except Exception as e:
        logger.error("nexus_worker_bootstrap_failed", error=str(e))

@celery_app.task(name="nexus.analyze", queue="pillar.nexus")
def nexus_task(job_id: str):
    """Primary orchestrator task for multi-source reasoning."""
    logger.info("nexus_task_received", job_id=job_id)
    return asyncio.run(_execute_nexus(job_id))

async def _execute_nexus(job_id: str):
    import os
    import json
    from datetime import datetime, timezone
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.use_cases.retrieval.run_pipeline import run_nexus_pipeline

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logger.error("nexus_missing_database_url")
        return {"error": "DATABASE_URL not set"}

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            res = await db.execute(
                text("SELECT source_id, multi_source_ids, question FROM analysis_jobs WHERE id = :job_id"),
                {"job_id": job_id}
            )
            job = res.fetchone()
            if not job:
                return {"error": "Job not found"}
                
            source_id, multi_source_ids, question_raw = job
            all_sources = [str(source_id)]
            if multi_source_ids:
                all_sources.extend([str(sid) for sid in multi_source_ids])
            
            parsed_text = question_raw
            try:
                q_data = json.loads(question_raw)
                if isinstance(q_data, dict) and "text" in q_data:
                    parsed_text = q_data["text"]
            except Exception:
                pass
                
            payload = {
                "job_id": job_id,
                "source_ids": all_sources,
                "question": parsed_text
            }
            
            result = await run_nexus_pipeline(payload)
            
            current_report = result.get("insight_report") or "Nexus analysis complete."
            synthesis_report = "### ⚡ STRATEGIC NEXUS SYNTHESIS\n" + current_report
            status = "error" if result.get("status") == "error" else "done"
            
            await db.execute(
                text("UPDATE analysis_jobs SET status = :status, synthesis_report = :report, completed_at = :now WHERE id = :job_id"),
                {"status": status, "report": synthesis_report, "now": datetime.now(timezone.utc), "job_id": job_id}
            )
            
            await db.execute(
                text("""
                INSERT INTO analysis_results (job_id, insight_report, exec_summary) 
                VALUES (:job_id, :insight, :exec_summary)
                ON CONFLICT (job_id) DO UPDATE SET 
                insight_report = EXCLUDED.insight_report, exec_summary = EXCLUDED.exec_summary
                """),
                {"job_id": job_id, "insight": current_report, "exec_summary": "Nexus Synthesis Summary"}
            )
            
            await db.commit()
            return {"status": status}
    except Exception as e:
        logger.error("nexus_pipeline_db_failed", error=str(e), job_id=job_id)
        async with async_session() as db:
            await db.execute(
                text("UPDATE analysis_jobs SET status = 'error', error_message = :err WHERE id = :job_id"),
                {"err": str(e), "job_id": job_id}
            )
            await db.commit()
        return {"error": str(e)}
    finally:
        await engine.dispose()

