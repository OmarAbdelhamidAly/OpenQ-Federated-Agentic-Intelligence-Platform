"""Tests for authentication endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_happy_path(client: AsyncClient):
    """POST /auth/register creates tenant + admin and returns tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "New Corp",
            "email": "newuser@example.com",
            "password": "StrongPass123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering with the same email twice returns 409."""
    payload = {
        "tenant_name": "Corp A",
        "email": "duplicate@example.com",
        "password": "StrongPass123",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_happy_path(client: AsyncClient):
    """POST /auth/login with valid creds returns tokens."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Login Corp",
            "email": "login@example.com",
            "password": "StrongPass123",
        },
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """POST /auth/login with wrong password returns 401."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Wrong Corp",
            "email": "wrong@example.com",
            "password": "StrongPass123",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "BadPassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_happy_path(client: AsyncClient):
    """POST /auth/refresh with valid refresh token returns new tokens."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Refresh Corp",
            "email": "refresh@example.com",
            "password": "StrongPass123",
        },
    )
    refresh_token = reg.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """POST /auth/refresh with invalid token returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_no_token(client: AsyncClient):
    """Accessing protected endpoint without token returns 403."""
    response = await client.get("/api/v1/data-sources")
    assert response.status_code == 403
