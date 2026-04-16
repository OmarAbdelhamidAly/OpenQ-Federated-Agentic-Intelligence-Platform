"""SQLAlchemy model for the task_submissions table."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from sqlalchemy import ForeignKey, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_tasks.id"), nullable=False
    )
    submitter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Text submission
    attachments: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # URLs to files/evidence
    
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    task = relationship("CorporateTask", backref="submissions")
