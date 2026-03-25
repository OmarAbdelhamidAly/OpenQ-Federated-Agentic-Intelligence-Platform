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

# ── 2. Specialist Pillars (SQL, CSV, PDF, JSON) ──────────────────────────────

@celery_app.task(bind=True, name="pillar_task", max_retries=3)
def pillar_task(self, job_id: str) -> dict:
    """Executes the core specialist analysis logic."""
    return asyncio.run(_execute_pillar(job_id))

async def _execute_pillar(job_id: str) -> dict:
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    from app.models.data_source import DataSource
    from app.use_cases.analysis.run_pipeline import get_pipeline

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

            thread_id = str(job.id)
            config = {"configurable": {"thread_id": thread_id}}
            
            pipeline = get_pipeline(source.type, checkpointer=checkpointer)

            # NEW: Check for existing checkpoint and metadata for immediate pause/resume logic
            checkpoint = await checkpointer.aget_tuple(config)
            
            # NEW: Persist metadata even if pausing (for SQL visibility during HITL)
            if checkpoint and checkpoint.metadata:
                from sqlalchemy import update
                await db.execute(
                    update(AnalysisJob)
                    .where(AnalysisJob.id == uuid.UUID(job_id))
                    .values(
                        generated_sql=checkpoint.metadata.get("generated_sql"),
                        intent=checkpoint.metadata.get("intent")
                    )
                )
                await db.commit()

            if checkpoint and checkpoint.metadata.get("source") == "interrupt":
                job.status = "awaiting_approval"
                await db.commit() # Commit status change
                logger.info("job_paused_for_approval", job_id=job_id, next_nodes=checkpoint.next)
                return {"status": "awaiting_approval"}

            existing_state = await pipeline.aget_state(config)
            is_resuming = bool(existing_state.next)
            
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

            graph_input = None if is_resuming else {
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "question": parsed_text,
                "history": parsed_history,
                "source_id": str(job.source_id),
                "source_type": source.type,
                "kb_id": str(job.kb_id) if job.kb_id else None,
            }

            logger.info("graph_execution_started", job_id=job_id, is_resuming=is_resuming, start_node=existing_state.next)

            async for event in pipeline.astream(
                graph_input,
                config,
                stream_mode="updates",
            ):
                if "__metadata__" not in event:
                    for node_name, state_update in event.items():
                        # Skip special langgraph events that are not node updates
                        if node_name.startswith("__") or not isinstance(state_update, dict):
                            logger.info("graph_special_event", node=node_name, type=str(type(state_update)), job_id=job_id)
                            continue
                            
                        logger.info("graph_node_update", node=node_name, keys=list(state_update.keys()), job_id=job_id)
                        
                        # Update job thinking steps
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
            
            # Update Job Metadata (Always capture latest SQL/Intent regardless of completion)
            job.generated_sql = res_data.get("generated_sql") or job.generated_sql
            job.intent = res_data.get("intent") or job.intent
            
            if graph_state.next:
                 job.status = "awaiting_approval"
                 logger.info("job_paused_for_approval", job_id=job_id, next_nodes=graph_state.next)
            else:
                  logger.info("saving_analysis_results", 
                              job_id=job_id, 
                              has_chart=res_data.get("chart_json") is not None, 
                              insight_len=len(res_data.get("insight_report") or ""))
                  
                  # Update Job Metadata
                  job.generated_sql = res_data.get("generated_sql") or job.generated_sql
                  job.intent = res_data.get("intent") or job.intent
                  
                  # Save Analysis Results (Upsert)
                  # Mapping ORM attributes to their database column names for absolute consistency
                  from sqlalchemy.dialects.postgresql import insert
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
        logger.error("pillar_execution_failed", error=str(e), job_id=job_id)
        async with async_session_factory() as db:
            from sqlalchemy import update
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == uuid.UUID(job_id))
                .values(status="error", error_message=str(e))
            )
            await db.commit()
        return {"error": str(e)}
    finally:
        # ── Loop Safety ──
        # In Celery with prefork, a process is reused but asyncio.run starts a NEW loop.
        # Global objects like the SQL engine or Redis client must be cleared/closed
        # to prevent "attached to a different loop" errors.
        try:
            from app.infrastructure.database.postgres import engine
            await engine.dispose()
            await redis_client.aclose()
        except Exception:
            pass

# ── 3. Source Discovery (Profiling Phase) ────────────────────────────────────

@celery_app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles a CSV/SQL data source and triggers auto-analysis."""
    return asyncio.run(_execute_source_discovery(source_id, user_id))

async def _execute_source_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource
    import pandas as pd
    import os

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("discovery_source_not_found", source_id=source_id)
            return

        logger.info("discovery_started", source_id=source_id, type=source.type)
        
        try:
            schema_json = {}
            if source.type == "csv" and source.file_path:
                df = pd.read_csv(source.file_path)
                from app.routers.data_sources import _profile_dataframe
                schema_json = _profile_dataframe(df)
            elif source.type == "sql":
                from app.routers.data_sources import _profile_sqlite
                # If it's a file-based sqlite
                if source.file_path and os.path.exists(source.file_path):
                    schema_json = _profile_sqlite(source.file_path)
            
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
