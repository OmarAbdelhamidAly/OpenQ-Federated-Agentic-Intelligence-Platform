"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class InviteUserRequest(BaseModel):
    """POST /users/invite — admin invites a new user to the tenant."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["admin", "viewer"]


class UserResponse(BaseModel):
    """Single user representation."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """GET /users — list of users in the tenant (admin only)."""
    users: List[UserResponse]
