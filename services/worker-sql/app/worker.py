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
    from app.models.metric import BusinessMetric
    from app.models.policy import SystemPolicy
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

            thread_id = f"{job.id}_{source.type}"
            config = {"configurable": {"thread_id": thread_id}}
            
            pipeline = get_pipeline(source.type, checkpointer=checkpointer)

            # Persist metadata even if pausing (for SQL visibility during HITL)
            graph_state = await pipeline.aget_state(config)
            if graph_state.values:
                from sqlalchemy import update
                await db.execute(
                    update(AnalysisJob)
                    .where(AnalysisJob.id == uuid.UUID(job_id))
                    .values(
                        generated_sql=graph_state.values.get("generated_sql"),
                        intent=graph_state.values.get("intent")
                    )
                )
                await db.commit()
                await db.refresh(job)

            # Transition to Awaiting Approval if graph interrupted
            is_at_interrupt = bool(graph_state.next)

            # Handle Human-in-the-loop (HITL) Resume Logic
            if is_at_interrupt:
                if job.status == "awaiting_approval":
                    logger.info("job_still_paused_waiting_for_user", job_id=job_id)
                    return {"status": "awaiting_approval"}
                
                # If we reach here and status is "running", it means the user approved via API.
                # We inject the flag into the state so the graph progresses past the interrupt.
                logger.info("injecting_approval_granted_flag", job_id=job_id)
                await pipeline.aupdate_state(config, {"approval_granted": True})

            existing_state = await pipeline.aget_state(config)
            is_resuming = bool(existing_state.next)
            
            m_result = await db.execute(select(BusinessMetric).where(BusinessMetric.tenant_id == job.tenant_id))
            metrics = [{"name": m.name, "definition": m.definition, "formula": m.formula or "N/A"} for m in m_result.scalars().all()]
            
            p_result = await db.execute(select(SystemPolicy).where(SystemPolicy.tenant_id == job.tenant_id))
            policies = [{"name": p.name, "type": p.rule_type, "description": p.description} for p in p_result.scalars().all()]

            graph_input = None if is_resuming else {
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "question": job.question,
                "source_id": str(job.source_id),
                "source_type": source.type,
                "kb_id": str(job.kb_id) if job.kb_id else None,
                "file_path": source.file_path,
                "config_encrypted": source.config_encrypted,
                "schema_summary": source.schema_json or {},
                "business_metrics": metrics,
                "system_policies": policies,
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
                 logger.info("job_paused_for_internal_human_feedback", job_id=job_id, next_nodes=graph_state.next)
            else:
                  logger.info("saving_pillar_analysis_results", job_id=job_id)
                  
                  # Save Analysis Results (Upsert)
                  # Mapping ORM attributes to their database column names for absolute consistency
                  from sqlalchemy.dialects.postgresql import insert
                  stmt = insert(AnalysisResult).values(
                      job_id=job.id,
                      chart_json=res_data.get("chart_json"),
                      chart_engine=res_data.get("chart_engine", "echarts"),
                      viz_rationale=res_data.get("viz_rationale"),
                      insight_report=res_data.get("insight_report"),
                      exec_summary=res_data.get("executive_summary"),
                      recommendations_json=res_data.get("recommendations"),
                      follow_up_suggestions=res_data.get("follow_up_suggestions"),
                  )
                  stmt = stmt.on_conflict_do_update(
                      index_elements=['job_id'],
                      set_={
                          'chart_json': stmt.excluded.chart_json,
                          'chart_engine': stmt.excluded.chart_engine,
                          'viz_rationale': stmt.excluded.viz_rationale,
                          'insight_report': stmt.excluded.insight_report,
                          'exec_summary': stmt.excluded.exec_summary,
                          'recommendations_json': stmt.excluded.recommendations_json,
                          'follow_up_suggestions': stmt.excluded.follow_up_suggestions,
                      }
                  )
                  await db.execute(stmt)
                  
                  # ── Master Strategist: Handoff Logic ──────────────────
                  current_report = res_data.get("insight_report") or res_data.get("executive_summary") or "Analysis complete."
                  pillar_name = source.type.upper() if source else "SQL"
                  
                  # Enrich the unified synthesis report
                  header = f"\n\n### 🛡️ SPECIALIST REPORT: {pillar_name} (Step {job.complexity_index}/{job.total_pills})\n"
                  job.synthesis_report = (job.synthesis_report or "") + header + current_report

                  if job.required_pillars and job.complexity_index < job.total_pills:
                      job.status = "awaiting_approval"
                      logger.info("sequential_step_paused", job_id=job_id, current_index=job.complexity_index)
                  else:
                      job.status = "done"
                      job.completed_at = datetime.now(timezone.utc)
                      logger.info("pillar_complete_final", job_id=job_id)

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
            from app.modules.sql.tools.run_sql_query import dispose_all_engines
            await engine.dispose()
            await dispose_all_engines()
            
            if 'redis_client' in locals():
                await redis_client.aclose()

            # ── Decisive httpx Cleanup ──
            # Search for any httpx.AsyncClient instances that might be leaked by agents
            # and close them within the current loop.
            import gc
            for obj in gc.get_objects():
                try:
                    import httpx
                    if isinstance(obj, httpx.AsyncClient) and not obj.is_closed:
                        logger.info("force_closing_leaked_httpx_client", client_id=id(obj))
                        await obj.aclose()
                except (Exception, ImportError):
                    continue

        except Exception as e:
            logger.warning("cleanup_error", error=str(e))
        
        # ── Final Task Cleanup ──
        # Ensure all pending tasks (like close-wait) are completed or cancelled
        try:
            pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if pending:
                logger.info("cancelling_pending_tasks", count=len(pending))
                for task in pending: task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
        except Exception:
            pass

# ── 3. Source Discovery (Profiling Phase) ────────────────────────────────────

@celery_app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles a SQL/SQLite data source and triggers auto-analysis."""
    return asyncio.run(_execute_source_discovery(source_id, user_id))

async def _execute_source_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource
    import os

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("discovery_source_not_found", source_id=source_id)
            return

        logger.info("discovery_started", source_id=source_id, type=source.type)
        
        try:
            if source.type == "sql":
                from app.modules.sql.agents.strategic_profiler_agent import strategic_sql_profiler
                # Strategic profiling includes LLM enrichment and Neo4j sync
                result = await strategic_sql_profiler(source_id)
                if "error" in result:
                     raise Exception(result["error"])
                
                logger.info("strategic_discovery_complete", source_id=source_id)
                # Trigger Nexus Stitching
                try:
                    celery_app.send_task("nexus.discovery", args=[source_id], queue="pillar.nexus")
                except Exception as e:
                    logger.warning("nexus_stitching_trigger_failed", error=str(e))
                return
            
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
