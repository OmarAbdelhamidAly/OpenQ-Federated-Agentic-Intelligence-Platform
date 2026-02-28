"""Pydantic schemas for analysis endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisQueryRequest(BaseModel):
    """POST /analysis/query — submit a natural-language question."""
    source_id: uuid.UUID
    question: str = Field(..., min_length=1, max_length=2000)


class AnalysisJobResponse(BaseModel):
    """Status of a single analysis job."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    source_id: uuid.UUID
    question: str
    intent: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class RecommendationItem(BaseModel):
    """Individual recommendation from the agent pipeline."""
    action: str
    expected_impact: str
    confidence_score: int = Field(..., ge=0, le=100)
    main_risk: str


class AnalysisResultResponse(BaseModel):
    """Full analysis result — always contains all 5 fields."""
    job_id: uuid.UUID
    chart_json: Optional[Dict[str, Any]] = None
    insight_report: Optional[str] = None
    executive_summary: Optional[str] = None
    recommendations: Optional[List[RecommendationItem]] = None
    follow_up_suggestions: Optional[List[str]] = None

    model_config = {"from_attributes": True}


class AnalysisHistoryResponse(BaseModel):
    """GET /analysis/history — list of jobs with optional results."""
    jobs: List[AnalysisJobResponse]
