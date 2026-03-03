"""File storage utilities for tenant-scoped file operations."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import UploadFile

BASE_DIR = "/tmp/tenants"


def get_tenant_dir(tenant_id: str) -> Path:
    """Return (and create) the tenant's base directory."""
    path = Path(BASE_DIR) / tenant_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_exports_dir(tenant_id: str) -> Path:
    """Return (and create) the tenant's exports directory."""
    path = get_tenant_dir(tenant_id) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload_file(upload: UploadFile, tenant_id: str) -> str:
    """Save an uploaded file to the tenant's directory.

    Returns the absolute file path.
    """
    tenant_dir = get_tenant_dir(tenant_id)
    file_path = tenant_dir / (upload.filename or "unnamed_file")

    # Handle duplicate filenames by appending a counter
    counter = 1
    original_stem = file_path.stem
    original_suffix = file_path.suffix
    while file_path.exists():
        file_path = tenant_dir / f"{original_stem}_{counter}{original_suffix}"
        counter += 1

    content = await upload.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return str(file_path)


def delete_tenant_files(tenant_id: str) -> None:
    """Delete all files for a tenant (used for cleanup)."""
    tenant_dir = Path(BASE_DIR) / tenant_id
    if tenant_dir.exists():
        shutil.rmtree(tenant_dir)
