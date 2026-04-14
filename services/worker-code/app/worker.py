import os
import asyncio
import structlog
from celery import Celery
from celery.signals import worker_init

from app.use_cases.ingestion.service import run_codebase_ingestion

logger = structlog.get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "worker-code",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "process_codebase_indexing": {"queue": "pillar.code"},
        "pillar_task":               {"queue": "pillar.codebase"},
    },
)

# ---------------------------------------------------------------------------
# One-time startup bootstrap
# ---------------------------------------------------------------------------
# `worker_init` fires exactly once when the Celery worker process starts,
# before it begins consuming tasks.  We use it to:
#   1. Warm up the Neo4j driver singleton (first connection + pool fill).
#   2. Ensure all structural and full-text indexes exist in Neo4j.
#
# This avoids doing index-creation queries inside every task invocation
# (the old behaviour with _ensure_constraints() in __init__).
# ---------------------------------------------------------------------------

@worker_init.connect
def on_worker_init(**kwargs):
    logger.info("worker_code_init_started")
    try:
        from app.infrastructure.neo4j_adapter import bootstrap_neo4j
        import asyncio
        asyncio.run(bootstrap_neo4j())
        logger.info("worker_code_init_finished")
    except Exception as exc:
        # Non-fatal — the worker can still start; tasks will fail gracefully
        # if Neo4j is unreachable and log the error clearly.
        logger.error("worker_code_init_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.task(name="process_codebase_indexing", bind=True)
def process_codebase_indexing(self, source_id: str):
    logger.info("process_codebase_indexing_started", source_id=source_id)
    asyncio.run(run_codebase_ingestion(source_id))
    # NEW: Trigger Strategic Nexus Stitching
    try:
        app.send_task("nexus.discovery", args=[source_id], queue="pillar.nexus")
        logger.info("nexus_stitching_triggered", source_id=source_id)
    except Exception as e:
        logger.warning("nexus_stitching_trigger_failed", error=str(e))
    logger.info("process_codebase_indexing_finished", source_id=source_id)


@app.task(name="pillar_task", bind=True)
def pillar_task(self, job_id: str):
    logger.info("pillar_task_started", job_id=job_id)
    return asyncio.run(_execute_pillar(job_id))

async def _execute_pillar(job_id: str):
    import json
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.use_cases.analysis.run_pipeline import run_codebase_pipeline
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        # Fallback for local development or disconnected tests
        return {"error": "DATABASE_URL not set in worker-code environment"}

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Query the AnalysisJob
            res = await db.execute(
                text("SELECT tenant_id, user_id, source_id, complexity_index, total_pills, question, synthesis_report FROM analysis_jobs WHERE id = :job_id"),
                {"job_id": job_id}
            )
            job = res.fetchone()
            if not job:
                return {"error": "Job not found"}
                
            tenant_id, user_id, source_id, complexity_index, total_pills, question_raw, current_synthesis = job
            
            # Parse question payload for session_id, memory, etc.
            parsed_text = question_raw
            session_id = None
            try:
                q_data = json.loads(question_raw)
                if isinstance(q_data, dict) and "text" in q_data:
                    parsed_text = q_data["text"]
                    session_id = q_data.get("session_id")
            except Exception:
                pass
                
            logger.info("codebase_pipeline_triggering", source=str(source_id), session_id=session_id)
            
            # Run LangGraph Agent Pipeline - we pass the FULL question_raw so the pipeline can parse `history`
            result = await run_codebase_pipeline(
                question=question_raw, 
                source_id=str(source_id), 
                tenant_id=str(tenant_id),
                session_id=session_id
            )
            
            # Parse final state
            current_report = result.get("insight_report") or result.get("executive_summary") or "Analysis complete."
            synthesis_report = (current_synthesis or "") + "\n\n### 🛡️ SPECIALIST REPORT: CODEBASE (Step " + str(complexity_index) + "/" + str(total_pills) + ")\n" + current_report
            
            # Update AnalysisJob explicitly
            status = "awaiting_approval" if complexity_index < total_pills else "done"
            await db.execute(
                text("UPDATE analysis_jobs SET status = :status, synthesis_report = :report, completed_at = :now WHERE id = :job_id"),
                {"status": status, "report": synthesis_report, "now": datetime.now(timezone.utc), "job_id": job_id}
            )
            
            # Upsert into AnalysisResult table
            await db.execute(
                text("""
                INSERT INTO analysis_results (job_id, insight_report, exec_summary) 
                VALUES (:job_id, :insight, :exec_summary)
                ON CONFLICT (job_id) DO UPDATE SET 
                insight_report = EXCLUDED.insight_report, exec_summary = EXCLUDED.exec_summary
                """),
                {"job_id": job_id, "insight": result.get("insight_report"), "exec_summary": result.get("executive_summary")}
            )
            
            await db.commit()
            return {"status": status}
    except Exception as e:
        logger.error("codebase_pillar_failed", error=str(e), job_id=job_id)
        async with async_session() as db:
            await db.execute(
                text("UPDATE analysis_jobs SET status = 'error', error_message = :err WHERE id = :job_id"),
                {"err": str(e), "job_id": job_id}
            )
            await db.commit()
        return {"error": str(e)}
    finally:
        await engine.dispose()


@app.task(name="ping")
def ping():
    return "pong"
