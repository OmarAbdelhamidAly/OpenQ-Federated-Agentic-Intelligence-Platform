"""SQLAlchemy model for the org_nodes table."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import ForeignKey, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class OrgNode(Base):
    __tablename__ = "org_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_nodes.id"), nullable=True
    )
    
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Internal path for Materialized Path queries: "uuid1.uuid2.uuid3"
    path: Mapped[str] = mapped_column(Text, index=True, nullable=False)
    
    node_type: Mapped[str] = mapped_column(
        String(50), default="department" # e.g., "headquarters", "branch", "department", "team"
    )

    node_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    parent = relationship("OrgNode", remote_side=[id], backref="children")
