"""SQLAlchemy model for the analysis_results table."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id"),
        primary_key=True,
    )
    chart_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # ECharts or Plotly figure JSON
    chart_engine: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default="echarts"
    )  # "echarts" | "plotly"
    insight_report: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Full written analysis
    executive_summary: Mapped[Optional[str]] = mapped_column(
        "exec_summary", Text, nullable=True
    )  # Max 3-sentence summary
    recommendations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        "recommendations_json", JSON, nullable=True
    )  # List of recommendation objects
    follow_up_suggestions: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )  # List of follow-up questions
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        JSON, nullable=True
    )  # Vector embedding for historical memory search

    visual_context: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )

    # Relationships
    job = relationship("AnalysisJob", back_populates="result")
