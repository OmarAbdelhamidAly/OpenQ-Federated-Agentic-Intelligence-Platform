"""Celery worker — PDF/Knowledge Base Specialized Pillar."""
import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from celery import Celery
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "analyst_worker_pdf",
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
    broker_transport_options={
        'visibility_timeout': 14400,  # 4 hours to allow for large AI model downloads
    },
)

@celery_app.task(bind=True, name="pillar_task", max_retries=3)
def pillar_task(self, job_id: str) -> dict:
    """Executes the PDF/KB analysis logic."""
    return asyncio.run(_execute_pillar(job_id))

async def _execute_pillar(job_id: str) -> dict:
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    from app.models.data_source import DataSource
    from app.modules.pdf.workflow import build_pdf_graph

    # Instantiate fresh checkpointer for the current loop
    import redis.asyncio as redis
    from langgraph.checkpoint.redis import AsyncRedisSaver
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    # Bind job_id so all logs in this task have it automatically
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(job_id=job_id)

    try:
        async with async_session_factory() as db:
            res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
            job = res.scalar_one_or_none()
            if not job: return {"error": "Job not found"}

            ds_res = await db.execute(select(DataSource).where(DataSource.id == job.source_id))
            source = ds_res.scalar_one_or_none()
            source_type = source.type if source else "pdf"

            # Determine which pipeline mode was used for this source
            analysis_mode = "deep_vision"
            if source and source.schema_json:
                analysis_mode = source.schema_json.get("indexing_mode", "deep_vision")
            
            thread_id = str(job.id)
            config = {"configurable": {"thread_id": thread_id}}
            
            pipeline = build_pdf_graph(checkpointer=checkpointer, mode=analysis_mode)
            logger.info("pdf_pipeline_mode", job_id=job_id, mode=analysis_mode)

            parsed_text = job.question
            parsed_history = []
            try:
                import json
                q_data = json.loads(job.question)
                if isinstance(q_data, dict) and "text" in q_data:
                    parsed_text = q_data["text"]
                    parsed_history = q_data.get("history", [])
            except:
                pass

            graph_input = {
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "question": parsed_text,
                "history": parsed_history,
                "source_id": str(job.source_id),
                "source_type": source.type if source else "pdf",
                "kb_id": str(job.kb_id) if job.kb_id else None,
            }

            logger.info("pdf_graph_execution_started", job_id=job_id)

            async for event in pipeline.astream(
                graph_input,
                config,
                stream_mode="updates",
            ):
                if "__metadata__" not in event:
                    for node_name, state_update in event.items():
                        logger.info("graph_node_update", node=node_name, job_id=job_id)
                        
                        current_steps = list(job.thinking_steps or [])
                        current_steps.append({
                            "node": node_name, 
                            "status": "completed", 
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        job.thinking_steps = current_steps
                        await db.commit()

            # Final state retrieval
            graph_state = await pipeline.aget_state(config)
            res_data = graph_state.values
            
            logger.info("pdf_graph_final_state", 
                        job_id=job_id, 
                        has_report=bool(res_data.get("insight_report")),
                        has_visual=bool(res_data.get("visual_context")),
                        visual_count=len(res_data.get("visual_context") or []))

            # Save Analysis Results (Upsert)
            from sqlalchemy.dialects.postgresql import insert
            stmt = insert(AnalysisResult).values(
                job_id=job.id,
                chart_json=res_data.get("chart_json"),
                insight_report=res_data.get("insight_report"),
                exec_summary=res_data.get("executive_summary"),
                recommendations_json=res_data.get("recommendations"),
                follow_up_suggestions=res_data.get("follow_up_suggestions"),
                visual_context=res_data.get("visual_context"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['job_id'],
                set_={
                    'chart_json': stmt.excluded.chart_json,
                    'insight_report': stmt.excluded.insight_report,
                    'exec_summary': stmt.excluded.exec_summary,
                    'recommendations_json': stmt.excluded.recommendations_json,
                    'follow_up_suggestions': stmt.excluded.follow_up_suggestions,
                    'visual_context': stmt.excluded.visual_context,
                }
            )
            await db.execute(stmt)
            
            job.status = "done"
            job.completed_at = datetime.now(timezone.utc)
            logger.info("pillar_complete_final", job_id=job_id)
            
            # Trigger semantic cache
            report_text = res_data.get("insight_report") or res_data.get("executive_summary") or ""
            if report_text:
                try:
                    celery_app.send_task("cache_result_task", args=[parsed_text, report_text, str(job.tenant_id)], queue="governance")
                except Exception as e:
                    logger.warning("cache_trigger_failed", error=str(e))
            await db.commit()
            
            return {"status": "done"}

    except Exception as e:
        logger.error("pdf_pillar_failed", error=str(e), job_id=job_id)
        async with async_session_factory() as db:
            from sqlalchemy import update
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == uuid.UUID(job_id))
                .values(status="error", error_message=str(e))
            )
            await db.commit()
        return {"error": str(e)}
# ── 3. Document Indexing (Knowledge Service) ──────────────────────────────────

@celery_app.task(name="process_document_indexing")
def process_document_indexing(doc_id: str):
    """Indices a PDF document using the specialized PDF worker."""
    return asyncio.run(_execute_indexing(doc_id))

@celery_app.task(name="process_source_indexing")
def process_source_indexing(source_id: str):
    """Indices a PDF DataSource using the specialized PDF worker."""
    return asyncio.run(_execute_source_indexing(source_id))

async def _execute_source_indexing(source_id: str):
    from app.modules.pdf.flows.deep_vision.agents.indexing_agent import indexing_agent_source
    from app.modules.pdf.flows.fast_text.agents.fast_indexing_agent import fast_indexing_agent
    from app.models.data_source import DataSource
    from app.infrastructure.database.postgres import async_session_factory
    from sqlalchemy import select

    print(f"\n[STRATEGIC SIGNAL] RECEIVED SOURCE INDEXING TASK: {source_id}")
    logger.info("source_indexing_task_received", source_id=source_id)

    # Determine indexing_mode from DataSource
    indexing_mode = "deep_vision"  # default
    try:
        async with async_session_factory() as db:
            res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
            src = res.scalar_one_or_none()
            if src and src.schema_json:
                indexing_mode = src.schema_json.get("indexing_mode", "deep_vision")
    except Exception as e:
        logger.warning("indexing_mode_lookup_failed", error=str(e))

    logger.info("indexing_mode_selected", source_id=source_id, mode=indexing_mode)

    if indexing_mode == "fast_text":
        result = await fast_indexing_agent(source_id)
    else:
        result = await indexing_agent_source(source_id)

    print(f"[STRATEGIC SIGNAL] INDEXING COMPLETED FOR {source_id}: {result.get('status')}")

    if result.get("status") == "success":
        print(f"[STRATEGIC SIGNAL] TRIGGERING AUTO-ANALYSIS FOR {source_id}")
        celery_app.send_task(
            "auto_analysis_task",
            args=[source_id, "00000000-0000-0000-0000-000000000000"],
            queue="governance"
        )

    return result

async def _execute_indexing(doc_id: str):
    from app.modules.pdf.flows.deep_vision.agents.indexing_agent import indexing_agent
    logger.info("indexing_task_received", doc_id=doc_id)
    result = await indexing_agent(doc_id)
    return result
