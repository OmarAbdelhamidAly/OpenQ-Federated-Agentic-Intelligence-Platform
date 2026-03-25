"""SQLAlchemy model for the system_policies table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres import Base


class SystemPolicy(Base):
    """Stores data governance and compliance rules (e.g. 'Never show SSN')."""
    __tablename__ = "system_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)  # cleaning, compliance, security
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    tenant = relationship("Tenant")


class ResourcePolicy(Base):
    """
    Advanced IAM: Principal-Action-Resource model.
    Defines who (Principal) can do what (Action) to which (Resource).
    """
    __tablename__ = "resource_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    principal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )  # User ID or Team ID
    
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # "query", "upload", "delete", "*"
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)  # DataSource UUID or "pillar.*" or "*"
    effect: Mapped[str] = mapped_column(String(10), default="allow")  # "allow" | "deny"
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    tenant = relationship("Tenant")
    principal_user = relationship("User", foreign_keys=[principal_id], primaryjoin="ResourcePolicy.principal_id == User.id")
