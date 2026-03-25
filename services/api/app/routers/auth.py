"""Authentication router — register, login, refresh (all public)."""



import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import settings
from app.infrastructure.database.postgres import get_db
from app.infrastructure.middleware import limiter
from app.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.infrastructure.token_blacklist import (
    is_refresh_token_valid,
    revoke_refresh_token,
    store_refresh_token,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.user import (
    InviteUserRequest,
    UserListResponse,
    UserResponse,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")  # Prevent mass account creation
async def register(
    request: Request,
    body: Annotated[RegisterRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Create a new tenant and its first admin user."""

    # Check if email already exists
    existing = await db.execute(
        select(User)
        .where(User.email == body.email)
        .options(selectinload(User.tenant))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create tenant
    tenant = Tenant(id=uuid.uuid4(), name=body.tenant_name)
    db.add(tenant)
    await db.flush()

    # Create admin user
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    logger.info(
        "user_registered",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        email=body.email,
        role="admin",
    )

    token_data = {
        "sub": str(user.id),
        "tenant_id": str(tenant.id),
        "role": user.role,
    }
    refresh_token = create_refresh_token(token_data)
    # Store JTI in Redis so this token can be revoked on logout
    refresh_payload = decode_token(refresh_token)
    await store_refresh_token(
        jti=refresh_payload["jti"],
        user_id=str(user.id),
        ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  # Prevent brute-force password guessing
async def login(
    request: Request,
    body: Annotated[LoginRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with email + password and receive JWT tokens."""

    result = await db.execute(
        select(User)
        .where(User.email == body.email)
        .options(selectinload(User.tenant))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "user_logged_in",
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        email=body.email,
        role=user.role,
    )

    token_data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }
    refresh_token = create_refresh_token(token_data)
    # Store JTI in Redis so this token can be revoked on logout
    refresh_payload = decode_token(refresh_token)
    await store_refresh_token(
        jti=refresh_payload["jti"],
        user_id=str(user.id),
        ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: Annotated[RefreshRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""

    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        old_jti = payload.get("jti")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Reject if this token has been revoked (e.g. user logged out)
    if old_jti and not await is_refresh_token_valid(old_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please log in again.",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Revoke the old token before issuing new one (token rotation)
    if old_jti:
        await revoke_refresh_token(old_jti)

    token_data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }
    new_refresh = create_refresh_token(token_data)
    new_payload = decode_token(new_refresh)
    await store_refresh_token(
        jti=new_payload["jti"],
        user_id=str(user.id),
        ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    body: Annotated[RefreshRequest, Body()],
) -> Response:
    """Revoke the provided refresh token immediately (logout)."""
    try:
        payload = decode_token(body.refresh_token)
        jti = payload.get("jti")
        if jti:
            await revoke_refresh_token(jti)
            logger.info("user_logged_out", jti=jti)
    except JWTError:
        # Token already expired or invalid — no action needed
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
