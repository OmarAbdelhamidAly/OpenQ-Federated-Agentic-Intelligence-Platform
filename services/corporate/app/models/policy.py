"""SQLAlchemy model for the corporate_policies table."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from sqlalchemy import ForeignKey, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class CorporatePolicy(Base):
    __tablename__ = "corporate_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    category: Mapped[str] = mapped_column(String(50), default="general") # "financial", "security", "hr", "operations"
    severity: Mapped[str] = mapped_column(String(20), default="warning") # "info", "warning", "critical"
    
    # Optional mapping to specific nodes (if policy only applies to some departments)
    # If null, applies to the whole organization
    node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_nodes.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    node = relationship("OrgNode", backref="policies")
