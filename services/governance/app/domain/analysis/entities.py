"""Shared AnalysisState TypedDict used across the LangGraph pipeline."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict
import operator

def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer to merge dictionaries instead of overwriting."""
    return {**(left or {}), **(right or {})}


def safe_append(left: Optional[List[Any]], right: Optional[List[Any]]) -> List[Any]:
    """Reducer to append items to a list, handling None values."""
    if left is None:
        return right or []
    if right is None:
        return left
    return left + right


def safe_concat(left: Optional[str], right: Optional[str]) -> str:
    """Reducer to concatenate strings, handling None values."""
    if not left:
        return right or ""
    if not right:
        return left
    return left + "\n" + right


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

    # ── Vision 2026: Multi-Agentic Orchestration ───────────────
    required_pillars: Optional[List[str]]  # e.g. ["sql", "pdf"]
    multi_source_ids: Optional[List[str]]
    synthesis_report: Optional[str]
    selected_sources: Optional[List[Dict[str, Any]]] # [{id, type, name, schema}]

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
    analysis_results: Annotated[Optional[Dict[str, Any]], merge_dicts]

    # ── Visualization Agent Output ────────────────────────────
    chart_json: Annotated[Optional[Dict[str, Any]], merge_dicts]  # Plotly figure JSON

    # ── Insight Agent Output ──────────────────────────────────
    insight_report: Optional[str]
    executive_summary: Optional[str]

    # ── Recommendation Agent Output ───────────────────────────
    recommendations: Annotated[Optional[List[Dict[str, Any]]], safe_append]
    follow_up_suggestions: Annotated[Optional[List[str]], safe_append]

    # ── Conversational Memory ─────────────────────────────────
    history: Annotated[Optional[List[Dict[str, str]]], safe_append]  # List of {role, content}
    thread_id: Optional[str]
    
    # ── HITL ──────────────────────────────────────────────────
    validation_results: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    approval_granted: bool
    
    # ── Reflection & Refinement ──────────────────────────────
    reflection_context: Optional[str]
    reflection_count: int
    user_feedback: Optional[str]

    # ── Error Handling ────────────────────────────────────────
    error: Optional[str]
    retry_count: int
    intermediate_steps: Annotated[Optional[List[Dict[str, Any]]], safe_append]

    # ── Progressive Complexity ────────────────────────────────
    complexity_index: int        # Current index in a batch (1-indexed)
    total_pills: int            # Total number of pills in the batch
