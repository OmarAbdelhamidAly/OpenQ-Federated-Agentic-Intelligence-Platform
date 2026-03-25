"""Celery worker — JSON Specialized Pillar."""
import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from celery import Celery
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "analyst_worker_json",
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

@celery_app.task(bind=True, name="pillar_task", max_retries=3)
def pillar_task(self, job_id: str) -> dict:
    """Executes the core JSON specialist logic."""
    return asyncio.run(_execute_pillar(job_id))

async def _execute_pillar(job_id: str) -> dict:
    import sqlalchemy
    from sqlalchemy import select, update
    from sqlalchemy.dialects.postgresql import insert
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    from app.models.data_source import DataSource
    from app.modules.json.workflow import build_json_graph

    # Instantiate fresh checkpointer for the current loop
    import redis.asyncio as redis
    from langgraph.checkpoint.redis import AsyncRedisSaver
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    # Initialize MongoDB client
    from app.infrastructure.mongo_client import MongoDBClient
    await MongoDBClient.connect()

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

            thread_id = str(job.id)
            config = {"configurable": {"thread_id": thread_id}}
            
            pipeline = build_json_graph(checkpointer=checkpointer)

            # Check for existing checkpoint
            checkpoint = await checkpointer.aget_tuple(config)
            
            if checkpoint and checkpoint.metadata:
                await db.execute(
                    update(AnalysisJob)
                    .where(AnalysisJob.id == uuid.UUID(job_id))
                    .values(intent=checkpoint.metadata.get("intent"))
                )
                await db.commit()

            if checkpoint and checkpoint.metadata.get("source") == "interrupt":
                job.status = "awaiting_approval"
                await db.commit()
                return {"status": "awaiting_approval"}

            existing_state = await pipeline.aget_state(config)
            is_resuming = bool(existing_state.next)
            
            graph_input = None
            if not is_resuming:
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
                    "source_type": source.type,
                    "file_path": source.file_path,
                    "kb_id": str(job.kb_id) if job.kb_id else None,
                }

            logger.info("json_graph_execution_started", job_id=job_id, is_resuming=is_resuming)

            async for event in pipeline.astream(
                graph_input,
                config,
                stream_mode="updates",
            ):
                if "__metadata__" not in event:
                    for node_name, state_update in event.items():
                        if node_name.startswith("__") or not isinstance(state_update, dict):
                            continue
                            
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
            
            if graph_state.next:
                 job.status = "awaiting_approval"
            else:
                  # Save Analysis Results (Upsert)
                  stmt = insert(AnalysisResult).values(
                      job_id=job.id,
                      chart_json=res_data.get("chart_json"),
                      insight_report=res_data.get("insight_report"),
                      exec_summary=res_data.get("executive_summary"),
                      recommendations_json=res_data.get("recommendations"),
                      follow_up_suggestions=res_data.get("follow_up_suggestions"),
                  )
                  stmt = stmt.on_conflict_do_update(
                      index_elements=['job_id'],
                      set_={
                          'chart_json': stmt.excluded.chart_json,
                          'insight_report': stmt.excluded.insight_report,
                          'exec_summary': stmt.excluded.exec_summary,
                          'recommendations_json': stmt.excluded.recommendations_json,
                          'follow_up_suggestions': stmt.excluded.follow_up_suggestions,
                      }
                  )
                  await db.execute(stmt)
                  
                  # ── Vision 2026: Multi-Agentic Coordination ──────────
                  if job.required_pillars and len(job.required_pillars) > 1:
                      job.status = "done" # Mark partial done
                      celery_app.send_task("synthesis_task", args=[job_id], queue="governance")
                      logger.info("pillar_complete_triggered_synthesis", job_id=job_id)
                  else:
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
            return {"status": job.status}

    except Exception as e:
        logger.error("json_pillar_failed", error=str(e), job_id=job_id)
        async with async_session_factory() as db:
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == uuid.UUID(job_id))
                .values(status="error", error_message=str(e))
            )
            await db.commit()
        return {"error": str(e)}
    finally:
        try:
            from app.infrastructure.database.postgres import engine
            await engine.dispose()
            await redis_client.aclose()
            await MongoDBClient.close()
        except Exception:
            pass

# ── 3. Source Discovery (Profiling Phase) ────────────────────────────────────

@celery_app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles a JSON data source and triggers auto-analysis."""
    return asyncio.run(_execute_source_discovery(source_id, user_id))

async def _execute_source_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource
    import json as json_lib
    import os

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("discovery_source_not_found", source_id=source_id)
            return

        logger.info("discovery_started", source_id=source_id, type="json")
        
        try:
            schema_json = {"source_type": "json"}
            if source.file_path and os.path.exists(source.file_path):
                with open(source.file_path, "r") as f:
                    data = json_lib.load(f)
                    if isinstance(data, list):
                        schema_json["item_count"] = len(data)
                        if len(data) > 0 and isinstance(data[0], dict):
                            schema_json["fields"] = list(data[0].keys())
                    elif isinstance(data, dict):
                        schema_json["field_count"] = len(data.keys())
                        schema_json["fields"] = list(data.keys())
            
            source.schema_json = schema_json
            source.indexing_status = "done"
            await db.commit()
            
            # Trigger Auto-Analysis
            celery_app.send_task(
                "auto_analysis_task", 
                args=[source_id, user_id], 
                queue="governance"
            )
            logger.info("discovery_complete_triggered_analysis", source_id=source_id)
            
        except Exception as e:
            logger.error("discovery_failed", source_id=source_id, error=str(e))
            source.indexing_status = "failed"
            await db.commit()
