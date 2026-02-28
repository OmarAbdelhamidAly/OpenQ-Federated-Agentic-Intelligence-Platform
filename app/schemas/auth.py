"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """POST /auth/register — create a new tenant + admin user."""
    tenant_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """POST /auth/login."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """POST /auth/refresh — exchange a refresh token for new tokens."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Returned on successful login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
