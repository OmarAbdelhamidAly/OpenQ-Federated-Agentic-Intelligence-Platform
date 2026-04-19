"""Celery worker — Universal Document Intelligence Pillar.

Supported document types for indexing and analysis:
  PDF, DOCX, DOC, ODT, PPTX, PPT, XLSX, CSV, TSV,
  EML, MSG, RTF, EPUB, HTML, XML, TXT, MD,
  PNG, JPG, JPEG (image-only documents via OCR)
"""
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
    from app.models.metric import BusinessMetric
    from app.models.policy import SystemPolicy
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

            # Map source type to Unstructured strategy and analysis mode
            # This ensures the same strategy used at index time is used at query time
            _TYPE_TO_INFO = {
                "pdf": {"mode": "deep_vision", "strategy": "auto"},
                "docx": {"mode": "fast_text",  "strategy": "fast"},
                "doc":  {"mode": "fast_text",  "strategy": "fast"},
                "odt":  {"mode": "fast_text",  "strategy": "fast"},
                "pptx": {"mode": "fast_text",  "strategy": "auto"},
                "ppt":  {"mode": "fast_text",  "strategy": "auto"},
                "xlsx": {"mode": "fast_text",  "strategy": "auto"},
                "csv":  {"mode": "fast_text",  "strategy": "fast"},
                "tsv":  {"mode": "fast_text",  "strategy": "fast"},
                "txt":  {"mode": "fast_text",  "strategy": "fast"},
                "md":   {"mode": "fast_text",  "strategy": "fast"},
                "html": {"mode": "fast_text",  "strategy": "fast"},
                "epub": {"mode": "fast_text",  "strategy": "fast"},
                "eml":  {"mode": "fast_text",  "strategy": "fast"},
                "msg":  {"mode": "fast_text",  "strategy": "fast"},
                "rtf":  {"mode": "fast_text",  "strategy": "fast"},
                "png":  {"mode": "hybrid",     "strategy": "ocr_only"},
                "jpg":  {"mode": "hybrid",     "strategy": "ocr_only"},
                "jpeg": {"mode": "hybrid",     "strategy": "ocr_only"},
            }
            type_info = _TYPE_TO_INFO.get(source_type, {"mode": "fast_text", "strategy": "auto"})

            # Determine which pipeline mode was used for this source
            # Priority: schema_json override > type default
            analysis_mode = "fast_text"
            if source and source.schema_json:
                analysis_mode = source.schema_json.get("indexing_mode",
                               type_info["mode"])
            
            thread_id = f"{job.id}_{source.type}"
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

            m_result = await db.execute(select(BusinessMetric).where(BusinessMetric.tenant_id == job.tenant_id))
            metrics = [{"name": m.name, "definition": m.definition, "formula": m.formula or "N/A"} for m in m_result.scalars().all()]
            
            p_result = await db.execute(select(SystemPolicy).where(SystemPolicy.tenant_id == job.tenant_id))
            policies = [{"name": p.name, "type": p.rule_type, "description": p.description} for p in p_result.scalars().all()]

            graph_input = {
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "question": parsed_text,
                "history": parsed_history,
                "source_id": str(job.source_id),
                "source_type": source.type if source else "pdf",
                "file_path": source.file_path if source else None,
                "kb_id": str(job.kb_id) if job.kb_id else None,
                "analysis_mode": analysis_mode,
                "config_encrypted": source.config_encrypted if source else None,
                "schema_summary": source.schema_json or {} if source else {},
                "business_metrics": metrics,
                "system_policies": policies,
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
                evaluation_metrics=res_data.get("evaluation_metrics"),
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
                    'evaluation_metrics': stmt.excluded.evaluation_metrics,
                }
            )
            await db.execute(stmt)
            
            # ── Master Strategist: Handoff Logic ─────────────────────────
            # Use the succinct executive summary rather than the full insight report
            # to prevent UI duplication in single-pillar queries.
            current_report = res_data.get("executive_summary") or res_data.get("insight_report") or "Analysis complete."
            pillar_name = source.type.upper() if source else "PDF"
            
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
            
            # Trigger semantic cache for final or partial results
            if current_report:
                try:
                    celery_app.send_task("cache_result_task", args=[parsed_text, current_report, str(job.tenant_id)], queue="governance")
                except Exception as e:
                    logger.warning("cache_trigger_failed", error=str(e))
                    
            await db.commit()
            return {"status": job.status}

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
    from app.modules.pdf.flows.strategic_nexus.agents.nexus_strategic_indexer import strategic_nexus_indexer
    from app.modules.pdf.flows.hybrid_ocr.agents.hybrid_indexing_agent import hybrid_indexing_agent
    from app.modules.pdf.utils.unstructured_partitioner import recommend_strategy
    from app.models.data_source import DataSource
    from app.infrastructure.database.postgres import async_session_factory
    from sqlalchemy import select

    print(f"\n[UNIVERSAL DOC] RECEIVED SOURCE INDEXING TASK: {source_id}")
    logger.info("source_indexing_task_received", source_id=source_id)

    # Determine indexing_mode from DataSource (based on source type and user preference)
    indexing_mode = "fast_text"   # universal default
    source_file_type = "pdf"
    try:
        async with async_session_factory() as db:
            res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
            src = res.scalar_one_or_none()
            if src:
                source_file_type = src.type or "pdf"
                if src.schema_json:
                    indexing_mode = src.schema_json.get("indexing_mode", "fast_text")
                # Ensure doc_strategy is stored in schema_json for later retrieval
                doc_strategy = recommend_strategy(src.file_path or "", indexing_mode)
                if src.schema_json is None:
                    src.schema_json = {}
                src.schema_json["doc_strategy"] = doc_strategy
                from sqlalchemy import update
                await db.execute(
                    update(DataSource)
                    .where(DataSource.id == uuid.UUID(source_id))
                    .values(schema_json=src.schema_json)
                )
                await db.commit()
    except Exception as e:
        logger.warning("indexing_mode_lookup_failed", error=str(e))

    logger.info("indexing_mode_selected", source_id=source_id, mode=indexing_mode)

    results = []
    
    # 1. Always run Fast Text (Base Layer)
    logger.info("running_base_indexing", mode="fast_text")
    results.append(await fast_indexing_agent(source_id))

    # 2. Add Hybrid OCR Layer if requested
    if indexing_mode == "hybrid":
        logger.info("running_hybrid_layer", mode="hybrid_indexing")
        results.append(await hybrid_indexing_agent(source_id))

    # 3. Add Deep Vision Layer if requested
    if indexing_mode == "deep_vision":
        logger.info("running_vision_layer", mode="deep_vision")
        results.append(await indexing_agent_source(source_id))

    # 4. Add Strategic Nexus Layer (Flow 4) if requested
    if indexing_mode == "strategic_nexus":
        logger.info("running_strategic_nexus_layer", mode="strategic_nexus")
        results.append(await strategic_nexus_indexer(source_id))

    # Determine final status
    final_status = "success" if all(r.get("status") == "success" for r in results if isinstance(r, dict)) else "partial_failure"
    
    logger.info("tiered_indexing_completed", source_id=source_id, final_status=final_status)

    if final_status == "success":
        celery_app.send_task(
            "auto_analysis_task",
            args=[source_id, "00000000-0000-0000-0000-000000000000"],
            queue="governance"
        )
    
    # NEW: Trigger Strategic Nexus Stitching
    try:
        celery_app.send_task(
            "nexus.discovery", 
            args=[source_id], 
            queue="pillar.nexus"
        )
        logger.info("nexus_stitching_triggered", source_id=source_id)
    except Exception as e:
        logger.warning("nexus_stitching_trigger_failed", error=str(e))

    return {"status": final_status, "modes": [r.get("mode") for r in results if isinstance(r, dict)]}

async def _execute_indexing(doc_id: str):
    from app.modules.pdf.flows.deep_vision.agents.indexing_agent import indexing_agent
    logger.info("indexing_task_received", doc_id=doc_id)
    result = await indexing_agent(doc_id)
    return result
