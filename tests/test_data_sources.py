"""Tests for data source endpoints."""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient

from app.models.data_source import DataSource
from app.models.user import User


@pytest.mark.asyncio
async def test_list_data_sources_both_roles(
    client: AsyncClient, admin_token: str, viewer_token: str
):
    """Both admin and viewer can list data sources — returns 200."""
    for token in [admin_token, viewer_token]:
        response = await client.get(
            "/api/v1/data-sources",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "data_sources" in response.json()


@pytest.mark.asyncio
async def test_upload_csv_admin_success(
    client: AsyncClient, admin_token: str
):
    """Admin can upload a CSV file — returns 201."""
    csv_content = b"name,value\nAlice,100\nBob,200\nCharlie,300"
    response = await client.post(
        "/api/v1/data-sources/upload",
        files={"file": ("test_data.csv", io.BytesIO(csv_content), "text/csv")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "csv"
    assert data["name"] == "test_data.csv"
    assert data["schema_json"]["row_count"] == 3


@pytest.mark.asyncio
async def test_upload_csv_viewer_forbidden(
    client: AsyncClient, viewer_token: str
):
    """Viewer cannot upload files — returns 403."""
    csv_content = b"name,value\nAlice,100"
    response = await client.post(
        "/api/v1/data-sources/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_invalid_extension(
    client: AsyncClient, admin_token: str
):
    """Uploading unsupported file type returns 400."""
    response = await client.post(
        "/api/v1/data-sources/upload",
        files={"file": ("test.json", io.BytesIO(b"{}"), "application/json")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_connect_sql_admin_success(
    client: AsyncClient, admin_token: str
):
    """Admin can connect a SQL database — returns 201."""
    response = await client.post(
        "/api/v1/data-sources/connect-sql",
        json={
            "name": "Production DB",
            "engine": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "username": "readonly_user",
            "password": "secret",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "sql"
    assert data["name"] == "Production DB"


@pytest.mark.asyncio
async def test_connect_sql_viewer_forbidden(
    client: AsyncClient, viewer_token: str
):
    """Viewer cannot connect SQL databases — returns 403."""
    response = await client.post(
        "/api/v1/data-sources/connect-sql",
        json={
            "name": "Blocked DB",
            "engine": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "username": "user",
            "password": "pass",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_data_source_admin(
    client: AsyncClient, admin_token: str
):
    """Admin can delete a data source — returns 204."""
    # First upload
    csv_content = b"a,b\n1,2"
    upload = await client.post(
        "/api/v1/data-sources/upload",
        files={"file": ("del.csv", io.BytesIO(csv_content), "text/csv")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    source_id = upload.json()["id"]

    # Delete
    response = await client.delete(
        f"/api/v1/data-sources/{source_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_data_source_viewer_forbidden(
    client: AsyncClient, viewer_token: str
):
    """Viewer cannot delete data sources — returns 403."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(
        f"/api/v1/data-sources/{fake_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
