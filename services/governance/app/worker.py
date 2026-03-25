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
    broker_transport_options={
        "visibility_timeout": 14400,  # 4 hours
    }
)

# ── 1. Governance Layer (Intent + Policies) ───────────────────────────────────

@celery_app.task(bind=True, name="governance_task", max_retries=3)
def governance_task(self, job_id: str) -> dict:
    """Handles business metrics, intent detection, and safety guardrails."""
    return asyncio.run(_execute_governance(job_id))

async def _execute_governance(job_id: str) -> dict:
    from sqlalchemy import select, update
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.data_source import DataSource
    from app.models.metric import BusinessMetric
    from app.models.policy import SystemPolicy
    from app.models.tenant import Tenant

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

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            
            # Initial thinking step
            job.thinking_steps = [{
                "node": "starting_governance",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
            await db.commit()

            # ── Vision 2026: Fetch All Relevant Schemas ──────────────────────
            # Include both the primary source and any additional multi-sources
            all_source_ids = [job.source_id]
            if job.multi_source_ids:
                all_source_ids.extend([uuid.UUID(str(sid)) for sid in job.multi_source_ids if str(sid) != str(job.source_id)])
            
            ds_res = await db.execute(select(DataSource).where(DataSource.id.in_(all_source_ids)))
            sources = ds_res.scalars().all()
            
            selected_sources_meta = []
            primary_source = None
            for s in sources:
                if s.id == job.source_id: 
                    primary_source = s
                selected_sources_meta.append({
                    "id": str(s.id),
                    "type": s.type,
                    "name": s.name,
                    "schema": s.schema_json or {}
                })
            
            if not primary_source: return {"error": "Primary source not found"}

            # Build Initial State
            m_result = await db.execute(select(BusinessMetric).where(BusinessMetric.tenant_id == job.tenant_id))
            metrics = [{"name": m.name, "definition": m.definition, "formula": m.formula or "N/A"} for m in m_result.scalars().all()]
            
            p_result = await db.execute(select(SystemPolicy).where(SystemPolicy.tenant_id == job.tenant_id))
            policies = [{"name": p.name, "type": p.rule_type, "description": p.description} for p in p_result.scalars().all()]

            # ── Phase 3: Fetch Tenant for Persona ──────────────
            t_res = await db.execute(select(Tenant).where(Tenant.id == job.tenant_id))
            tenant = t_res.scalar_one_or_none()
            branding = tenant.branding_config if tenant else {}
            system_persona = branding.get("system_persona") if branding else None

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

            initial_state = {
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "question": parsed_text,
                "source_id": str(job.source_id),
                "kb_id": str(job.kb_id) if job.kb_id else None,
                "complexity_index": job.complexity_index,
                "total_pills": job.total_pills,
                "history": parsed_history,
                "source_type": primary_source.type,
                "file_path": primary_source.file_path,
                "config_encrypted": primary_source.config_encrypted,
                "schema_summary": primary_source.schema_json or {},
                "selected_sources": selected_sources_meta,
                "business_metrics": metrics,
                "system_policies": policies,
                "system_persona": system_persona,
                "retry_count": 0,
                "thread_id": str(job.id),
                "approval_granted": False,
            }

            # Update thinking: Intake starting
            current_steps = list(job.thinking_steps or [])
            current_steps.append({
                "node": "intake_analysis",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            job.thinking_steps = current_steps
            await db.commit()

            # Run Governance Phase (Intake -> Guardrail)
            from app.modules.governance.workflow import get_governance_pipeline
            pipeline = get_governance_pipeline(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": str(job.id)}}
            
            # Run the graph and stream events to update thinking steps
            async for event in pipeline.astream(initial_state, config, stream_mode="updates"):
                for node_name, state_update in event.items():
                    if node_name.startswith("__"): continue
                    
                    logger.info("governance_node_update", node=node_name, job_id=job_id)
                    
                    # Map graph nodes to human-friendly UI steps
                    ui_node = "safety_shield" if node_name == "guardrail" else node_name
                    
                    current_steps = list(job.thinking_steps or [])
                    current_steps.append({
                        "node": ui_node,
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    job.thinking_steps = current_steps
                    await db.commit()
            
            # Final Check
            final_state = await pipeline.aget_state(config)
            # Fast Track / Clarification
            if final_state.values.get("clarification_needed"):
                job.synthesis_report = final_state.values["clarification_needed"]
                job.status = "done"
                job.completed_at = datetime.now(timezone.utc)
                
                from app.models.analysis_result import AnalysisResult
                from sqlalchemy.dialects.postgresql import insert
                stmt = insert(AnalysisResult).values(
                    job_id=job.id,
                    insight_report=final_state.values["clarification_needed"],
                ).on_conflict_do_update(
                    index_elements=['job_id'],
                    set_={'insight_report': final_state.values["clarification_needed"]}
                )
                await db.execute(stmt)
                await db.commit()
                logger.info("governance_fast_track_completed", job_id=job_id)
                return {"status": "fast_track_done"}

            # Final Policy Check
            if final_state.values.get("policy_violation"):
                job.status = "error"
                job.error_message = f"Policy Violation: {final_state.values['policy_violation']}"
                await db.commit()
                return {"status": "policy_violation", "reason": final_state.values['policy_violation']}

            # ── Vision 2026: Sequential Master Strategist ─────────────────────
            # Implementation of User's "Search files one by one + feedback" vision
            
            # Identify the optimal sequence based on multi_source_ids
            all_ids = [str(job.source_id)]
            if job.multi_source_ids:
                all_ids.extend([str(sid) for sid in job.multi_source_ids if str(sid) != str(job.source_id)])
            
            # Map IDs to types to store in required_pillars for worker dispatch
            id_to_type = {str(s.id): s.type for s in sources}
            pillar_sequence = [id_to_type.get(sid, "csv") for sid in all_ids]
            
            job.required_pillars = pillar_sequence
            job.multi_source_ids = all_ids # Standardize the list
            
            # Start with the FIRST source
            job.complexity_index = 1 
            job.total_pills = len(pillar_sequence)
            await db.commit()

            # Dispatch ONLY the first pillar
            first_pillar = pillar_sequence[0]
            target_queue = f"pillar.{first_pillar.lower()}"
            celery_app.send_task("pillar_task", args=[job_id], queue=target_queue)
            
            logger.info("governance_sequential_start", job_id=job_id, pillar=first_pillar)
            return {"status": "sequential_dispatch_started", "first_pillar": first_pillar}

    except Exception as e:
        logger.error("governance_execution_failed", error=str(e), job_id=job_id)
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
        except Exception:
            pass

# ── 3. Auto-Analysis (Discovery Phase) ───────────────────────────────────────

@celery_app.task(name="auto_analysis_task")
def auto_analysis_task(source_id: str, user_id: str):
    """Triggers the domain discovery and smart question generation."""
    from app.use_cases.auto_analysis.service import run_auto_analysis
    from app.infrastructure.database.postgres import async_session_factory
    
    async def _run():
        async with async_session_factory() as db:
            await run_auto_analysis(source_id, user_id, db)
            
    return asyncio.run(_run())


# ── 4. Multi-Agentic Synthesis (Vision 2026) ──────────────────────────────────

@celery_app.task(name="synthesis_task")
def synthesis_task(job_id: str):
    """Merges results from multiple pillars into a unified insight."""
    return asyncio.run(_execute_synthesis(job_id))

async def _execute_synthesis(job_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult
    
    async with async_session_factory() as db:
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
        job = res.scalar_one_or_none()
        if not job: return
        
        # 2. Sequential Logic: Agentic Self-Evaluation (Vision 2026)
        # Check if we have more sources and if the current info is sufficient
        if job.complexity_index < job.total_pills:
            # Use LLM to suggest if we should continue
            from app.infrastructure.llm import get_llm
            eval_llm = get_llm(temperature=0)
            
            # Simple prompt to evaluate sufficiency
            eval_prompt = f"""
            Task: Evaluate if the current analysis is sufficient to answer the user's question.
            Question: {job.question}
            Current Findings: {job.synthesis_report}
            
            Based ONLY on the findings above, is the information SUFFICIENT to fully answer the question?
            Provide a 1-sentence recommendation followed by [SUFFICIENT] or [INSUFFICIENT].
            """
            eval_res = await eval_llm.ainvoke(eval_prompt)
            recommendation = eval_res.content if hasattr(eval_res, 'content') else str(eval_res)
            
            next_pillar = job.required_pillars[job.complexity_index]
            
            # Transition to awaiting_approval for user decision
            job.status = "awaiting_approval"
            job.synthesis_report = f"""
### 🧐 Intelligence Assessment
{recommendation}

---
**Current Progress**: Analyzed {job.required_pillars[job.complexity_index-1]} ({job.complexity_index}/{job.total_pills} sources)
**Next Potential Nexus**: {next_pillar}

**Recommendation**: Click 'Approve' to expand the search into {next_pillar}, or 'Cancel' if you are satisfied with the current insight.
"""
            await db.commit()
            logger.info("synthesis_paused_for_eval_feedback", job_id=job_id, recommendation=recommendation)
            return
            
        job.synthesis_report = "Integrated analysis complete across all selected sectors. No further search required."
        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Decode history pattern to extract question text for cache
        parsed_text = job.question
        try:
            import json
            q_data = json.loads(job.question)
            if isinstance(q_data, dict) and "text" in q_data:
                parsed_text = q_data["text"]
        except:
            pass
            
        try:
            celery_app.send_task("cache_result_task", args=[parsed_text, job.synthesis_report, str(job.tenant_id)], queue="governance")
        except:
            pass
        
        logger.info("synthesis_complete", job_id=job_id)

# ── 5. Semantic Cache Population ─────────────────────────────────────────────
@celery_app.task(name="cache_result_task", max_retries=2)
def cache_result_task(question: str, answer: str, tenant_id: str):
    """Saves a successfully completed analysis into the semantic vector cache."""
    return asyncio.run(_execute_cache_result(question, answer, tenant_id))

async def _execute_cache_result(question: str, answer: str, tenant_id: str):
    try:
        from app.modules.governance.agents.semantic_cache_agent import embed_text, get_qdrant
        from qdrant_client.models import Distance, VectorParams, PointStruct
        import uuid
        
        client = await get_qdrant()
        col_name = f"cache_{tenant_id.replace('-', '_')}"
        
        if not await client.collection_exists(col_name):
            await client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            
        vector = embed_text(question)
        await client.upsert(
            collection_name=col_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"question": question, "answer": answer}
                )
            ]
        )
        logger.info("semantic_cache_populated", tenant_id=tenant_id)
    except Exception as e:
        logger.warning("semantic_cache_population_failed", error=str(e))


# Specialized Governance Worker
