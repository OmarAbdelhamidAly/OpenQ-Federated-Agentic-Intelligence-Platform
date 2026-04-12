"""SQLAlchemy model for the data_sources table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import ForeignKey, String, Text, DateTime, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres import Base


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint("type IN ('csv', 'sql', 'document', 'pdf', 'json', 'codebase', 'image', 'audio', 'video')", name="ck_data_sources_type"),
        CheckConstraint("indexing_status IN ('pending', 'running', 'done', 'failed')", name="ck_data_sources_indexing_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "csv" | "sql" | "document" | "pdf" | "json" | "codebase" | "image" | "audio" | "video"
    name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # for CSV: /tmp/tenants/{tenant_id}/filename.csv
    config_encrypted: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # for SQL: AES-256 encrypted credentials JSON
    schema_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # column names, types, row count, sample values
    auto_analysis_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending"
    )  # "pending" | "running" | "done" | "failed"
    indexing_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="done"
    )  # "pending" | "running" | "done" | "failed" (done by default for non-PDF)
    auto_analysis_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # 5 auto-generated analysis results saved permanently
    domain_type: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # LLM-detected domain: "sales"|"hr"|"finance"|"inventory"|"customer"|"mixed"
    context_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # User-provided hint
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Last indexing error
    created_at: Mapped[datetime] = mapped_column(

        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="data_sources")
    analysis_jobs = relationship("AnalysisJob", back_populates="source", cascade="all, delete-orphan")
