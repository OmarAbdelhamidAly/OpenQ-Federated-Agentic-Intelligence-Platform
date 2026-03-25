"""SQLAlchemy model for the analysis_jobs table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'error', 'awaiting_approval')",
            name="ck_analysis_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # trend | comparison | ranking | correlation | anomaly
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    kb_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=True
    )
    generated_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thinking_steps: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )
    complexity_index: Mapped[int] = mapped_column(Integer, default=1)
    total_pills: Mapped[int] = mapped_column(Integer, default=1)
    
    # ── Vision 2026: Multi-Agentic Orchestration ───────────────
    required_pillars: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True
    )  # e.g. ["sql", "pdf"]
    synthesis_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    multi_source_ids: Mapped[Optional[list[uuid.UUID]]] = mapped_column(
        JSON, nullable=True
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="analysis_jobs")
    user = relationship("User", back_populates="analysis_jobs")
    source = relationship("DataSource", back_populates="analysis_jobs")
    result = relationship(
        "AnalysisResult", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
