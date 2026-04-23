"""Vision models for camera management and employee tracking logs."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import ForeignKey, String, Text, DateTime, Float, BIGINT
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class VisionCamera(Base):
    __tablename__ = "vision_cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    
    # Link to Corporate OrgNode (Room/Dept)
    org_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rtsp_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active") # active, offline, maintenance

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VisionFaceEmbedding(Base):
    __tablename__ = "vision_face_embeddings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True) # Linked to User
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    
    # Store face vector as an array of floats (FaceNet produces 128 or 512 dimensions)
    embedding: Mapped[List[float]] = mapped_column(ARRAY(Float), nullable=False)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class VisionLog(Base):
    """The central timeline for tracking employee activity."""
    __tablename__ = "vision_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vision_cameras.id"), nullable=False)
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    
    # activity examples: "focused_work", "on_phone", "away", "meeting"
    activity: Mapped[str] = mapped_column(String(50), nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0) # 0.0 to 1.0

    # JSON metadata for extra details (bbox, etc.)
    # Note: Not using JSON type here to keep dependencies simple for now, but can be added.
