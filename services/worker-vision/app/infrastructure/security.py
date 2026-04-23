"""Security dependencies for vision service."""
from __future__ import annotations
from fastapi import Header, HTTPException, status

async def require_admin(x_user_role: str = Header(None)):
    if not x_user_role or x_user_role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access vision data"
        )
    return x_user_role
