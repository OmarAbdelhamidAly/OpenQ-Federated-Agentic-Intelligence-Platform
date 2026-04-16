"""SQLAlchemy model for the corporate_tasks table."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from sqlalchemy import ForeignKey, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class CorporateTask(Base):
    __tablename__ = "corporate_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignee_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_nodes.id"), nullable=False
    )
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    status: Mapped[str] = mapped_column(
        String(20), default="active" # "draft", "active", "submitted", "approved", "rejected"
    )
    
    priority: Mapped[str] = mapped_column(String(10), default="medium") # "low", "medium", "high", "critical"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    node = relationship("OrgNode", backref="tasks")
