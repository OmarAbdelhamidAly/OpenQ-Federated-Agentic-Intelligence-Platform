"""SQLAlchemy model for the tenants table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="internal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    data_sources = relationship("DataSource", back_populates="tenant", cascade="all, delete-orphan")
    analysis_jobs = relationship("AnalysisJob", back_populates="tenant", cascade="all, delete-orphan")
