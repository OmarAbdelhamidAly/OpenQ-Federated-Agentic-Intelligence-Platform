"""Audio Intelligence Celery Worker.

Entry point for the pillar.audio queue.
Receives audio analysis tasks, runs the LangGraph pipeline,
and persists results to PostgreSQL.
"""
from __future__ import annotations

import os
import uuid
import structlog
from celery import Celery
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.infrastructure.config import settings
from app.infrastructure.database.postgres import async_session_factory, engine, Base

logger = structlog.get_logger(__name__)

# ── Celery App ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "worker_audio",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.worker.run_audio_analysis": {"queue": "pillar.audio"},
    },
)


# ── Main Task ─────────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.run_audio_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def run_audio_analysis(self, job_id: str, **kwargs):
    """Celery task wrapper — bridges sync Celery with async LangGraph pipeline."""
    import asyncio

    logger.info("audio_task_received", job_id=job_id)

    try:
        result = asyncio.run(_async_run_pipeline(job_id=job_id, **kwargs))
        return result
    except Exception as exc:
        logger.error("audio_task_failed", job_id=job_id, error=str(exc))
        try:
            asyncio.run(_mark_job_failed(job_id, str(exc)))
        except Exception:
            pass
        raise self.retry(exc=exc)


async def _async_run_pipeline(job_id: str, **kwargs) -> dict:
    """Run the full audio intelligence pipeline asynchronously."""
    from app.modules.audio.workflow import build_audio_graph
    from app.models.analysis_job import AnalysisJob
    from app.models.analysis_result import AnalysisResult

    async with async_session_factory() as db:
        # ── 1. Fetch Job ──────────────────────────────────────────────────────
        job_uuid = uuid.UUID(job_id)
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_uuid))
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update status to running
        job.status = "running"
        await db.commit()

        # ── 2. Build Initial State ────────────────────────────────────────────
        initial_state = {
            "tenant_id": str(job.tenant_id),
            "user_id": str(job.user_id),
            "job_id": job_id,
            "source_id": str(job.data_source_id),
            "question": job.question or "Provide a comprehensive analysis of this audio recording.",
            "file_path": job.file_path or "",
            "participant_names": job.extra_params.get("participant_names", []) if job.extra_params else [],
            "retry_count": 0,
        }

        # ── 3. Decision: Full Analysis vs Fast Retrieval ─────────────────────
        source_id = str(job.data_source_id)
        indexed = await _is_audio_indexed(source_id)
        
        if indexed:
            logger.info("audio_fast_retrieval_triggered", source_id=source_id)
            from app.modules.audio.agents.retrieval.retrieval_agent import audio_retrieval_agent
            retrieval_res = await audio_retrieval_agent(initial_state)
            
            from app.modules.audio.agents.indexing.summarizer_agent import summarizer_agent
            initial_state.update(retrieval_res)
            initial_state["speaker_turns"] = retrieval_res["retrieval_context"]["vector_hits"]
            
            final_res = await summarizer_agent(initial_state)
            output = {
                "insight_report": final_res.get("summary"),
                "executive_summary": "Fast-retrieval completed using GraphRAG.",
                "chunks_indexed": 0
            }
        else:
            # Run Full LangGraph Pipeline
            graph = build_audio_graph()
            final_state = await graph.ainvoke(initial_state)
            output = final_state.get("final_output", {})

        # ── 4. Persist Results ────────────────────────────────────────────────
        evaluation_metrics = output.get("evaluation_metrics")
        transcript_json = {
            "raw_transcript": output.get("raw_transcript", ""),
            "speaker_turns": output.get("speaker_turns", []),
            "speakers_map": output.get("speakers_map", {}),
            "speakers_count": output.get("speakers_count", 1),
            "language": output.get("transcript_language", "unknown"),
            "entities": output.get("entities", []),
            "action_items": output.get("action_items", []),
            "topics": output.get("topics", []),
            "key_quotes": output.get("key_quotes", []),
            "audio_duration_seconds": output.get("audio_duration_seconds", 0),
            "audio_format": output.get("audio_format", ""),
            "chunks_indexed": output.get("chunks_indexed", 0),
        }

        stmt = pg_insert(AnalysisResult).values(
            job_id=job_uuid,
            insight_report=output.get("insight_report"),
            exec_summary=output.get("executive_summary"),
            follow_up_suggestions=output.get("action_items", []),
            visual_context=[transcript_json],
            evaluation_metrics=evaluation_metrics,
        ).on_conflict_do_update(
            index_elements=["job_id"],
            set_={
                "insight_report": output.get("insight_report"),
                "exec_summary": output.get("executive_summary"),
                "follow_up_suggestions": output.get("action_items", []),
                "visual_context": [transcript_json],
                "evaluation_metrics": evaluation_metrics,
            },
        )
        await db.execute(stmt)

        # ── 5. Update Job Status ──────────────────────────────────────────────
        job.status = "failed" if output.get("error") else "done"
        await db.commit()

        # ── 6. Execute Semantic Weaver (Neo4j GDS GraphRAG) ──────────────────
        if job.status == "done":
            from app.use_cases.semantic_weaver import run_semantic_weaver
            # Fire and forget or await. We'll await to ensure it completes before worker finishes.
            logger.info("audio_triggering_semantic_weaver", job_id=job_id)
            try:
                await run_semantic_weaver(str(job.data_source_id))
            except Exception as e:
                logger.error("audio_semantic_weaver_failed_but_ignoring", job_id=job_id, error=str(e))

        logger.info(
            "audio_task_complete",
            job_id=job_id,
            status=job.status,
            speakers=output.get("speakers_count", 0),
            chunks=output.get("chunks_indexed", 0),
        )

        return {"job_id": job_id, "status": job.status}


async def _is_audio_indexed(source_id: str) -> bool:
    """Check if the audio source is already in Neo4j."""
    from app.infrastructure.neo4j_adapter import Neo4jAdapter
    neo4j = Neo4jAdapter()
    try:
        res = await neo4j.run_query(
            "MATCH (a:AudioSource {source_id: $source_id}) RETURN a.source_id",
            {"source_id": source_id}
        )
        return len(res) > 0
    except Exception:
        return False


async def _mark_job_failed(job_id: str, error: str):
    """Mark a job as failed in the database."""
    from app.models.analysis_job import AnalysisJob
    async with async_session_factory() as db:
        res = await db.execute(
            select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id))
        )
        job = res.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.last_error = error[:500]
            await db.commit()
