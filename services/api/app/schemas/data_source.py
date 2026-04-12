"""Pydantic schemas for data source endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SQLConnectionRequest(BaseModel):
    """POST /data-sources/connect-sql — admin connects a SQL database."""
    name: str = Field(..., min_length=1, max_length=200)
    engine: Literal["postgresql", "mysql", "mssql", "sqlite"]
    host: str
    port: int = Field(..., ge=1, le=65535)
    database: str
    username: str
    password: str


class GithubConnectionRequest(BaseModel):
    """POST /data-sources/connect-github — connect a github repo."""
    name: str = Field(..., min_length=1, max_length=200)
    github_url: str
    branch: str = "main"
    access_token: Optional[str] = None


class DataSourceResponse(BaseModel):
    """Single data source representation."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    type: str
    name: str
    file_path: Optional[str] = None
    schema_summary: Optional[Dict[str, Any]] = Field(None, validation_alias="schema_json", serialization_alias="schema_json")
    auto_analysis_status: str = "pending"   # pending | running | done | failed
    indexing_status: str = "done"           # pending | running | done | failed
    auto_analysis_json: Optional[Dict[str, Any]] = None
    domain_type: Optional[str] = None
    context_hint: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    """GET /data-sources — all data sources for the tenant."""
    data_sources: List[DataSourceResponse]
