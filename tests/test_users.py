"""Tests for user management endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_invite_user_admin_success(
    client: AsyncClient, admin_token: str
):
    """Admin can invite a new user — returns 201."""
    response = await client.post(
        "/api/v1/users/invite",
        json={
            "email": "newviewer@test.com",
            "password": "ViewerPass123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newviewer@test.com"
    assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_invite_user_viewer_forbidden(
    client: AsyncClient, viewer_token: str
):
    """Viewer cannot invite users — returns 403."""
    response = await client.post(
        "/api/v1/users/invite",
        json={
            "email": "blocked@test.com",
            "password": "BlockedPass123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_remove_user_admin_success(
    client: AsyncClient, admin_token: str, viewer_user: User
):
    """Admin can remove a user from the tenant — returns 204."""
    response = await client.delete(
        f"/api/v1/users/{viewer_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_remove_user_viewer_forbidden(
    client: AsyncClient, viewer_token: str, admin_user: User
):
    """Viewer cannot remove users — returns 403."""
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_remove_self_fails(
    client: AsyncClient, admin_token: str, admin_user: User
):
    """Admin cannot remove themselves — returns 400."""
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_users_admin(
    client: AsyncClient, admin_token: str
):
    """Admin can list all users in the tenant."""
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
