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
    kb_id: Optional[uuid.UUID] = None
    complexity_index: int = Field(default=1, ge=1)
    total_pills: int = Field(default=1, ge=1)
    multi_source_ids: Optional[List[uuid.UUID]] = None
    chat_history: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None


class AnalysisJobResponse(BaseModel):
    """Status of a single analysis job."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    source_id: uuid.UUID
    source_type: Optional[str] = None
    question: str
    intent: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    kb_id: Optional[uuid.UUID] = None
    generated_sql: Optional[str] = None
    error_message: Optional[str] = None
    thinking_steps: Optional[List[Dict[str, Any]]] = None
    multi_source_ids: Optional[List[uuid.UUID]] = None
    required_pillars: Optional[List[str]] = None
    synthesis_report: Optional[str] = None

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
    chart_engine: Optional[str] = "echarts"
    insight_report: Optional[str] = None
    executive_summary: Optional[str] = None
    recommendations_json: Optional[Any] = Field(default=None, validation_alias="recommendations")
    follow_up_suggestions: Optional[List[str]] = None
    visual_context: Optional[List[Dict[str, Any]]] = None
    generated_sql: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class AnalysisHistoryResponse(BaseModel):
    """GET /analysis/history — list of jobs with optional results."""
    jobs: List[AnalysisJobResponse]


class ProblemDiagnosisRequest(BaseModel):
    """POST /analysis/diagnose — describe a problem and get suggested scenarios."""
    source_id: uuid.UUID
    problem_description: str = Field(..., min_length=10, max_length=5000)


class DiagnosticScenario(BaseModel):
    """A suggested analytical scenario to diagnose a problem."""
    text: str
    reasoning: str
    impact: str
    priority: int = Field(..., ge=1, le=5)


class ProblemDiagnosisResponse(BaseModel):
    """Suggested scenarios resulting from problem diagnosis."""
    problem_summary: str
    suggestions: List[DiagnosticScenario]
