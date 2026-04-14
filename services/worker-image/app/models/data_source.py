"""SQLAlchemy model for the data_sources table — Image Worker."""

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
        CheckConstraint(
            "type IN ('csv', 'sql', 'document', 'pdf', 'json', 'image', 'audio', 'video', 'code')",
            name="ck_data_sources_type",
        ),
        CheckConstraint(
            "indexing_status IN ('pending', 'running', 'done', 'failed')",
            name="ck_data_sources_indexing_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    auto_analysis_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending"
    )
    indexing_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending"
    )
    auto_analysis_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    domain_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    context_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="data_sources")
    analysis_jobs = relationship(
        "AnalysisJob", back_populates="source", cascade="all, delete-orphan"
    )
