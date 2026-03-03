"""User management router — admin-only invite and remove."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres import get_db
from app.infrastructure.api_dependencies import get_current_user, require_admin
from app.infrastructure.security import hash_password
from app.models.user import User
from app.schemas.user import InviteUserRequest, UserListResponse, UserResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserListResponse:
    """List all users in the tenant (admin only)."""
    result = await db.execute(
        select(User).where(User.tenant_id == admin.tenant_id)
    )
    users = result.scalars().all()
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users])


@router.post(
    "/invite",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    body: InviteUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Invite a new user to the tenant (admin only)."""

    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(
        "user_invited",
        tenant_id=str(admin.tenant_id),
        invited_by=str(admin.id),
        new_user_id=str(user.id),
        email=body.email,
        role=body.role,
    )

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_user(
    user_id: uuid.UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove a user from the tenant (admin only)."""

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == admin.tenant_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself",
        )

    await db.delete(user)

    logger.info(
        "user_removed",
        tenant_id=str(admin.tenant_id),
        removed_by=str(admin.id),
        removed_user_id=str(user.id),
    )
