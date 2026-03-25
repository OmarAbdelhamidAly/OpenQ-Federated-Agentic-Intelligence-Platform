"""Pydantic schemas for group management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GroupCreateRequest(BaseModel):
    """POST /groups — admin creates a new group."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: Dict[str, Any] = Field(default_factory=dict)


class GroupUpdateRequest(BaseModel):
    """PATCH /groups/{id} — admin updates group info or permissions."""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None


class GroupResponse(BaseModel):
    """Base group representation."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: Dict[str, Any]
    created_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class GroupListResponse(BaseModel):
    """GET /groups — list of groups in the tenant."""
    groups: List[GroupResponse]
