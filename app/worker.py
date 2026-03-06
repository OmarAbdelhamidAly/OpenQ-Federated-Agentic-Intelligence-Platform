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
        
        # Load business metrics for the tenant
        from app.models.metric import BusinessMetric
        from app.models.policy import SystemPolicy
        m_result = await db.execute(
            select(BusinessMetric).where(BusinessMetric.tenant_id == job.tenant_id)
        )
        metrics = m_result.scalars().all()
        metrics_list = [
            {"name": m.name, "definition": m.definition, "formula": m.formula or "N/A"}
            for m in metrics
        ]

        if source is None:
            job.status = "error"
            job.error_message = "Data source not found"
            await db.commit()
            return {"error": "Data source not found"}

        # Build initial state
        thread_id = str(job.id)
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = {
            "tenant_id": str(job.tenant_id),
            "user_id": str(job.user_id),
            "question": job.question,
            "source_id": str(job.source_id),
            "source_type": source.type,
            "file_path": source.file_path,
            "config_encrypted": source.config_encrypted,
            "schema_summary": source.schema_json or {},
            "business_metrics": metrics_list,
            "kb_id": str(job.kb_id) if job.kb_id else None,
            "system_policies": [
                {"name": p.name, "type": p.rule_type, "description": p.description}
                for p in (await db.execute(
                    select(SystemPolicy).where(SystemPolicy.tenant_id == job.tenant_id)
                )).scalars().all()
            ],
            "retry_count": 0,
            "history": [],
            "thread_id": thread_id,
            "approval_granted": False,
        }

        try:
            # Run the correct pipeline (CSV or SQL) based on source type
            pipeline = get_pipeline(source.type)
            
            # Use astream to capture node transitions
            final_state = initial_state
            job.thinking_steps = []
            await db.commit()

            input_data = initial_state
            if job.status == "running" and job.generated_sql:
                input_data = None # Resuming from checkpointer

            async for event in pipeline.astream(input_data, config, stream_mode="updates"):
                # event is a dict where keys are node names and values are the state updates
                for node_name, state_update in event.items():
                    # Update final_state with local updates
                    final_state.update(state_update)
                    
                    # Log the node execution
                    current_steps = list(job.thinking_steps or [])
                    step_entry = {
                        "node": node_name,
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    
                    # If the node provided its own intermediate steps (like ReAct), include those
                    if "intermediate_steps" in state_update:
                        step_entry["details"] = state_update["intermediate_steps"]
                    
                    current_steps.append(step_entry)
                    job.thinking_steps = current_steps
                    
                    # Explicitly update status if we transitioned to a key node
                    if node_name == "analysis_generator":
                        job.status = "running"
                    
                    await db.commit()


            # Check if we interrupted for approval
            graph_state = await pipeline.aget_state(config)
            if graph_state.next:
                # We hit an interrupt (likely human_approval)
                job.status = "awaiting_approval"
                job.generated_sql = final_state.get("generated_sql")
                job.intent = final_state.get("intent")
                await db.commit()
                return {"status": "awaiting_approval", "job_id": job_id}

            # If we reached the end, save results
            analysis_result = AnalysisResult(
                job_id=job.id,
                chart_json=final_state.get("chart_json"),
                insight_report=final_state.get("insight_report"),
                exec_summary=final_state.get("executive_summary"),
                recommendations_json=final_state.get("recommendations"),
                follow_up_suggestions=final_state.get("follow_up_suggestions"),
            )
            db.add(analysis_result)

            # Persist enriched schema (ERD, etc.) back to the source
            if "schema_summary" in final_state:
                source.schema_json = final_state["schema_summary"]

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


@celery_app.task(name="process_document_indexing")
def process_document_indexing(doc_id: str):
    """Background task to extract text, chunk, embed, and index a document."""
    import asyncio
    return asyncio.run(_execute_indexing(doc_id))


async def _execute_indexing(doc_id: str):
    import pypdf
    import os
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.knowledge import Document
    from qdrant_client import QdrantClient

    async with async_session_factory() as db:
        res = await db.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
        doc = res.scalar_one_or_none()
        if not doc:
            return {"error": "Doc not found"}

        doc.status = "processing"
        await db.commit()

        try:
            # 1. Extract Text
            text = ""
            if doc.name.lower().endswith(".pdf"):
                with open(doc.file_path, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            else:
                with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            if not text.strip():
                raise ValueError("No text extracted from document")

            # 2. Chunking (Simple fixed-size chunks)
            chunk_size = 1000
            overlap = 200
            chunks = []
            for i in range(0, len(text), chunk_size - overlap):
                chunks.append(text[i:i + chunk_size])

            # 3. Embed & Index (Using Qdrant/FastEmbed)
            # Collection name = kb_<kb_id without hyphens>
            collection_name = f"kb_{str(doc.kb_id).replace('-', '')}"
            
            # Using Qdrant built-in fastembed support
            client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
            client.set_model("BAAI/bge-small-en-v1.5")
            
            # Upsert
            client.add(
                collection_name=collection_name,
                documents=chunks,
                metadata=[{"doc_id": str(doc.id), "kb_id": str(doc.kb_id), "name": doc.name} for _ in chunks]
            )

            doc.status = "indexed"
            await db.commit()
            return {"status": "success", "chunks": len(chunks)}

        except Exception as e:
            doc.status = "error"
            doc.metadata_json = {"error": str(e)}
            await db.commit()
            return {"error": str(e)}
        finally:
            from app.infrastructure.database.postgres import engine
            await engine.dispose()
