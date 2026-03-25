"""FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres import get_db, set_tenant_context
from app.infrastructure.security import decode_token
from app.models.user import User
from app.models.policy import ResourcePolicy

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT, load user from DB, and set RLS tenant context.

    Returns the authenticated ``User`` ORM instance.
    Raises 401 if the token is missing / invalid / expired or the user
    no longer exists.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .options(selectinload(User.group))
        .where(User.id == _uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Set RLS context so all subsequent queries in this session
    # are scoped to the authenticated user's tenant.
    await set_tenant_context(db, str(user.tenant_id))

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency that raises 403 unless the caller is an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def verify_permission(
    action: str,
    resource_id: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    Granular Principal-Action-Resource (PAR) check.
    If no policy exists, fallback to standard tenant-level visibility.
    """
    if current_user.role == "admin":
        return True

    # Check for explicit policies
    query = select(ResourcePolicy).where(
        ResourcePolicy.tenant_id == current_user.tenant_id,
        ResourcePolicy.principal_id == current_user.id
    )
    
    # Filter by action (exact or wildcard)
    query = query.where(ResourcePolicy.action.in_([action, "*"]))
    
    # Filter by resource (exact, pillar-wide, or wildcard)
    if resource_id:
        # Example: can match specific UUID, or "pillar.sql" if resource starts with "pillar."
        query = query.where(ResourcePolicy.resource_id.in_([resource_id, "*"]))

    result = await db.execute(query)
    policies = result.scalars().all()

    # If any DENY exists, 403 immediately
    if any(p.effect == "deny" for p in policies):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action '{action}' is explicitly denied for this resource."
        )

    # If an ALLOW exists, proceed
    if any(p.effect == "allow" for p in policies):
        return True

    # ── Vision 2026: Group-Level Resource Access ──────────────────
    if current_user.group and action == "query" and resource_id:
        accessible = current_user.group.permissions.get("accessible_sources")
        if accessible is not None:
            # If the list is defined, it's an allow-list
            if resource_id not in accessible:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This resource is not in your group's authorized access list."
                )

    # Fallback: For query/read actions, if no policy exists, we allow it 
    # as long as the resource belongs to the tenant (which get_current_user/RLS ensures).
    # But for destructive actions (delete), we might want to require explicit allow or admin.
    if action in ["delete", "modify"] and current_user.role != "admin":
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explicit permission required for this action."
        )

    return True
