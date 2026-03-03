"""Reports / export router — PDF, PNG, CSV downloads."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres import get_db
from app.infrastructure.api_dependencies import get_current_user
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.user import User
from app.use_cases.export.service import export_pdf, export_png, export_csv

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


async def _get_job_and_result(
    job_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> tuple[AnalysisJob, AnalysisResult]:
    """Shared helper — verify access and fetch job + result."""

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

    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.job_id == job_id)
    )
    analysis_result = result.scalar_one_or_none()
    if analysis_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not yet available",
        )

    return job, analysis_result


@router.get("/{job_id}/pdf")
async def download_pdf(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download analysis report as PDF."""
    job, result = await _get_job_and_result(job_id, current_user, db)
    tenant_id_str = str(current_user.tenant_id)

    file_path = export_pdf(
        tenant_id=tenant_id_str,
        job_id=str(job_id),
        question=job.question,
        executive_summary=result.exec_summary or "",
        insight_report=result.insight_report or "",
        recommendations=result.recommendations_json or [],
    )

    logger.info(
        "report_exported",
        tenant_id=tenant_id_str,
        user_id=str(current_user.id),
        job_id=str(job_id),
        format="pdf",
    )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"report_{job_id}.pdf",
    )


@router.get("/{job_id}/png")
async def download_png(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download chart as PNG image."""
    job, result = await _get_job_and_result(job_id, current_user, db)
    tenant_id_str = str(current_user.tenant_id)

    if not result.chart_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chart available for this analysis",
        )

    file_path = export_png(
        tenant_id=tenant_id_str,
        job_id=str(job_id),
        chart_json=result.chart_json,
    )

    logger.info(
        "report_exported",
        tenant_id=tenant_id_str,
        user_id=str(current_user.id),
        job_id=str(job_id),
        format="png",
    )

    return FileResponse(
        path=file_path,
        media_type="image/png",
        filename=f"chart_{job_id}.png",
    )


@router.get("/{job_id}/csv")
async def download_csv(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download analyzed data as CSV."""
    job, result = await _get_job_and_result(job_id, current_user, db)
    tenant_id_str = str(current_user.tenant_id)

    file_path = export_csv(
        tenant_id=tenant_id_str,
        job_id=str(job_id),
        chart_json=result.chart_json,
    )

    logger.info(
        "report_exported",
        tenant_id=tenant_id_str,
        user_id=str(current_user.id),
        job_id=str(job_id),
        format="csv",
    )

    return FileResponse(
        path=file_path,
        media_type="text/csv",
        filename=f"data_{job_id}.csv",
    )
