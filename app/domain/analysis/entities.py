"""Shared AnalysisState TypedDict used across the LangGraph pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AnalysisState(TypedDict, total=False):
    """State shared between all agent nodes in the LangGraph pipeline.

    Every field is optional by default (total=False) to allow
    incremental population across nodes.
    """

    # ── Input Context ─────────────────────────────────────────
    tenant_id: str
    user_id: str
    question: str
    source_id: str
    source_type: str             # "csv" | "sql"
    file_path: Optional[str]     # for CSV sources
    config_encrypted: Optional[str]  # for SQL sources
    business_metrics: Optional[List[Dict[str, str]]]  # List of {name, definition, formula}
    kb_id: Optional[str]         # UUID of the knowledge base to use for contextual RAG
    system_policies: Optional[List[Dict[str, str]]]  # List of {name, type, description}
    policy_violation: Optional[str]  # Error message if a guardrail is triggered

    # ── Intake Agent Output ───────────────────────────────────
    intent: str                  # trend | comparison | ranking | correlation | anomaly
    relevant_columns: List[str]
    time_range: Optional[str]
    clarification_needed: Optional[str]

    # ── Data Discovery Agent Output ───────────────────────────
    schema_summary: Dict[str, Any]
    data_quality_score: float    # 0.0–1.0

    # ── Data Cleaning Agent Output ────────────────────────────
    clean_dataframe_ref: Optional[str]  # path to cleaned CSV
    cleaning_log: Optional[List[str]]

    # ── Analysis Agent Output ─────────────────────────────────
    analysis_results: Optional[Dict[str, Any]]

    # ── Visualization Agent Output ────────────────────────────
    chart_json: Optional[Dict[str, Any]]  # Plotly figure JSON

    # ── Insight Agent Output ──────────────────────────────────
    insight_report: Optional[str]
    executive_summary: Optional[str]

    # ── Recommendation Agent Output ───────────────────────────
    recommendations: Optional[List[Dict[str, Any]]]
    follow_up_suggestions: Optional[List[str]]

    # ── Conversational Memory ─────────────────────────────────
    history: Optional[List[Dict[str, str]]]  # List of {role, content}
    thread_id: Optional[str]
    
    # ── HITL ──────────────────────────────────────────────────
    generated_sql: Optional[str]
    approval_granted: bool

    # ── Error Handling ────────────────────────────────────────
    error: Optional[str]
    retry_count: int
    intermediate_steps: Optional[List[Dict[str, Any]]]
