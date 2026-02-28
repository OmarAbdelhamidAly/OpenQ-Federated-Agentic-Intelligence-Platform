"""Pydantic schemas for report / export endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class ReportMetadata(BaseModel):
    """Metadata returned alongside export downloads."""
    job_id: uuid.UUID
    format: Literal["pdf", "png", "csv"]
    filename: str
