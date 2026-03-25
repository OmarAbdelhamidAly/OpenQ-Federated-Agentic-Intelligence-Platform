"""Analysis router — query, job status, history."""



import uuid
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres import get_db
from app.models.analysis_job import AnalysisJob
from app.infrastructure.api_dependencies import get_current_user, verify_permission
from app.models.analysis_result import AnalysisResult
from app.models.data_source import DataSource
from app.models.user import User
from app.schemas.analysis import (
    AnalysisHistoryResponse,
    AnalysisJobResponse,
    AnalysisQueryRequest,
    AnalysisResultResponse,
    ProblemDiagnosisRequest,
    ProblemDiagnosisResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post(
    "/query",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_query(
    body: Annotated[AnalysisQueryRequest, Body()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisJobResponse:
    """Submit a natural-language analysis question (both roles).

    Creates a pending analysis job and dispatches it to the Celery
    worker queue for async processing by the LangGraph agent pipeline.
    """

    # ── Phase 3: IAM Check ──────
    await verify_permission("query", str(body.source_id), current_user, db)
    
    # Also verify all multi-sources
    if body.multi_source_ids:
        for sid in body.multi_source_ids:
            await verify_permission("query", str(sid), current_user, db)

    # Verify source belongs to tenant (standard check)
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == body.source_id,
            DataSource.tenant_id == current_user.tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )

    import json
    actual_question = body.question
    if body.chat_history:
        actual_question = json.dumps({"text": body.question, "history": body.chat_history})

    job = AnalysisJob(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        source_id=body.source_id,
        multi_source_ids=body.multi_source_ids,
        question=actual_question,
        kb_id=body.kb_id,
        status="pending",
        thinking_steps=[],
        complexity_index=body.complexity_index,
        total_pills=body.total_pills,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Dispatch to Celery Governance Layer
    try:
        from app.worker import celery_app
        celery_app.send_task("governance_task", args=[str(job.id)], queue='governance')
    except Exception:
        # If Celery is not available, the job stays pending.
        # This is acceptable for MVP — the worker can pick it up later.
        logger.warning(
            "celery_dispatch_failed",
            job_id=str(job.id),
            tenant_id=str(current_user.tenant_id),
        )

    logger.info(
        "analysis_query_submitted",
        tenant_id=str(current_user.tenant_id),
        user_id=str(current_user.id),
        job_id=str(job.id),
        source_id=str(body.source_id),
        question=body.question,
    )

    return AnalysisJobResponse.model_validate(job)


@router.get("/history", response_model=AnalysisHistoryResponse)
async def get_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AnalysisHistoryResponse:
    """Get analysis history.

    - Admin: sees ALL jobs for the tenant.
    - Viewer: sees ONLY their own jobs.
    """
    query = select(AnalysisJob).where(
        AnalysisJob.tenant_id == current_user.tenant_id
    )

    # Viewers can only see their own jobs
    if current_user.role != "admin":
        query = query.where(AnalysisJob.user_id == current_user.id)

    query = query.order_by(AnalysisJob.started_at.desc().nullslast()).offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Fetch source types for all jobs in batch
    source_ids = [j.source_id for j in jobs]
    source_map = {}
    if source_ids:
        s_result = await db.execute(select(DataSource.id, DataSource.type).where(DataSource.id.in_(source_ids)))
        source_map = {row.id: row.type for row in s_result}

    import json
    response_jobs = []
    for j in jobs:
        rj = AnalysisJobResponse.model_validate(j)
        try:
            parsed = json.loads(rj.question)
            if isinstance(parsed, dict) and "text" in parsed:
                rj.question = parsed["text"]
        except:
            pass
        rj.source_type = source_map.get(j.source_id)
        response_jobs.append(rj)

    return AnalysisHistoryResponse(jobs=response_jobs)


@router.get("/{job_id}", response_model=AnalysisJobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisJobResponse:
    """Get a single analysis job status.

    - Admin: can view any job in the tenant.
    - Viewer: can only view their own jobs.
    """
    query = select(AnalysisJob).where(
        AnalysisJob.id == job_id,
        AnalysisJob.tenant_id == current_user.tenant_id,
    )

    # Viewers can only see their own jobs
    if current_user.role != "admin":
        query = query.where(AnalysisJob.user_id == current_user.id)

    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    import json
    rj = AnalysisJobResponse.model_validate(job)
    try:
        parsed = json.loads(rj.question)
        if isinstance(parsed, dict) and "text" in parsed:
            rj.question = parsed["text"]
    except:
        pass
    return rj


@router.get("/{job_id}/result", response_model=AnalysisResultResponse)
async def get_result(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisResultResponse:
    """Get the full analysis result for a completed job.

    - Admin: any job in the tenant.
    - Viewer: own jobs only.
    """
    # First verify job access
    job_query = select(AnalysisJob).where(
        AnalysisJob.id == job_id,
        AnalysisJob.tenant_id == current_user.tenant_id,
    )
    if current_user.role != "admin":
        job_query = job_query.where(AnalysisJob.user_id == current_user.id)

    job_result = await db.execute(job_query)
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    # Fetch result
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.job_id == job_id)
    )
    analysis_result = result.scalar_one_or_none()
    if analysis_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not yet available",
        )

    # Attach SQL and Engine from job for UI visibility
    response_data = AnalysisResultResponse.model_validate(analysis_result)
    response_data.generated_sql = job.generated_sql
    response_data.chart_engine = analysis_result.chart_engine or "echarts"
    
    return response_data


@router.post("/{job_id}/approve", response_model=AnalysisJobResponse)
async def approve_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisJobResponse:
    """Approve a paused analysis job and resume its execution."""
    query = select(AnalysisJob).where(
        AnalysisJob.id == job_id,
        AnalysisJob.tenant_id == current_user.tenant_id,
        AnalysisJob.status == "awaiting_approval",
    )
    
    if current_user.role != "admin":
        query = query.where(AnalysisJob.user_id == current_user.id)

    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paused analysis job not found",
        )

    # ── Vision 2026: Sequential Master Strategist ─────────────────────
    # If this was a sequential job awaiting feedback, increment and continue
    if job.required_pillars and job.complexity_index < job.total_pills:
        # Move to the NEXT source
        job.complexity_index += 1
        
        # In this master-strategist mode, we use multi_source_ids to find the next ID
        if job.multi_source_ids and len(job.multi_source_ids) >= job.complexity_index:
            next_source_id = job.multi_source_ids[job.complexity_index - 1]
            job.source_id = next_source_id
            
        next_pillar = job.required_pillars[job.complexity_index - 1]
        
        # Update state to running and resume
        job.status = "running"
        await db.commit()
        await db.refresh(job)

        target_queue = f"pillar.{next_pillar.lower()}"
        from app.worker import celery_app
        celery_app.send_task("pillar_task", args=[str(job.id)], queue=target_queue)
        logger.info("sequential_next_dispatched", job_id=str(job.id), pillar=next_pillar, index=job.complexity_index)
    else:
        # Legacy/Single-source approval logic
        job.status = "running"
        await db.commit()
        await db.refresh(job)
        
        source_res = await db.execute(select(DataSource.type).where(DataSource.id == job.source_id))
        source_type = source_res.scalar_one_or_none()
        target_queue = f"pillar.{source_type.lower()}" if source_type else "celery"
        
        from app.worker import celery_app
        celery_app.send_task("pillar_task", args=[str(job.id)], queue=target_queue)
        logger.info("approval_dispatched", job_id=str(job.id), queue=target_queue)

    return AnalysisJobResponse.model_validate(job)


@router.post("/diagnose", response_model=ProblemDiagnosisResponse)
async def submit_diagnosis(
    body: Annotated[ProblemDiagnosisRequest, Body()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProblemDiagnosisResponse:
    """Analyze a business problem and suggest diagnostic scenarios."""
    # Verify source belongs to tenant
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == body.source_id,
            DataSource.tenant_id == current_user.tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )

    from app.use_cases.analysis.diagnose_service import diagnose_problem
    
    # Use schema if available, otherwise suggest generic analysis
    schema = source.schema_json or {}
    diagnosis = await diagnose_problem(body.problem_description, schema)
    
    return ProblemDiagnosisResponse(**diagnosis)
