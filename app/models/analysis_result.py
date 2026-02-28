"""SQLAlchemy model for the analysis_results table."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id"),
        primary_key=True,
    )
    chart_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # Plotly figure JSON
    insight_report: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Full written analysis
    exec_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Max 3-sentence summary
    recommendations_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )  # List of recommendation objects
    follow_up_suggestions: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )  # List of follow-up questions

    # Relationships
    job = relationship("AnalysisJob", back_populates="result")
