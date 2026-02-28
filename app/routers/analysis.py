"""Analysis router — query, job status, history."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.data_source import DataSource
from app.models.user import User
from app.schemas.analysis import (
    AnalysisHistoryResponse,
    AnalysisJobResponse,
    AnalysisQueryRequest,
    AnalysisResultResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post(
    "/query",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_query(
    body: AnalysisQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisJobResponse:
    """Submit a natural-language analysis question (both roles).

    Creates a pending analysis job and dispatches it to the Celery
    worker queue for async processing by the LangGraph agent pipeline.
    """

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

    job = AnalysisJob(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        source_id=body.source_id,
        question=body.question,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Dispatch to Celery (import here to avoid circular deps)
    try:
        from app.worker import run_analysis_pipeline
        run_analysis_pipeline.delay(str(job.id))
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

    return AnalysisHistoryResponse(
        jobs=[AnalysisJobResponse.model_validate(j) for j in jobs]
    )


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

    return AnalysisJobResponse.model_validate(job)


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

    return AnalysisResultResponse.model_validate(analysis_result)
