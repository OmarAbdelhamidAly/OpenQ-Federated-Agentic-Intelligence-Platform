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
    """State shared between all agent nodes in the LangGraph pipeline."""

    # ── Input Context ─────────────────────────────────────────
    tenant_id: str
    user_id: str
    question: str
    source_id: str
    source_type: str             # "csv" | "sql" | "json"
    file_path: Optional[str]     
    config_encrypted: Optional[str]  
    business_metrics: Optional[List[Dict[str, str]]]  
    kb_id: Optional[str]         
    system_policies: Optional[List[Dict[str, str]]]  
    policy_violation: Optional[str]  

    # ── Intake Agent Output ───────────────────────────────────
    intent: str                  
    relevant_columns: List[str]
    time_range: Optional[str]
    clarification_needed: Optional[str]

    # ── Data Discovery Agent Output ───────────────────────────
    schema_summary: Dict[str, Any]
    data_quality_score: float    
    table_name: Optional[str]

    # ── Data Cleaning Agent Output ────────────────────────────
    clean_dataframe_ref: Optional[str]  
    cleaning_log: Optional[List[str]]

    # ── Analysis Agent Output ─────────────────────────────────
    analysis_results: Annotated[Optional[Dict[str, Any]], merge_dicts]

    # ── Visualization Agent Output ────────────────────────────
    chart_json: Annotated[Optional[Dict[str, Any]], merge_dicts]  

    # ── Insight Agent Output ──────────────────────────────────
    insight_report: Optional[str]
    executive_summary: Optional[str]

    # ── Recommendation Agent Output ───────────────────────────
    recommendations: Annotated[Optional[List[Dict[str, Any]]], safe_append]
    follow_up_suggestions: Annotated[Optional[List[str]], safe_append]

    # ── Conversational Memory ─────────────────────────────────
    history: Annotated[Optional[List[Dict[str, str]]], safe_append]  
    thread_id: Optional[str]
    
    # ── HITL ──────────────────────────────────────────────────
    validation_results: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    approval_granted: bool
    
    # ── Reflection & Refinement ──────────────────────────────
    reflection_context: Optional[str]
    reflection_count: int
    user_feedback: Optional[str]
    repaired_plan: Optional[Dict[str, Any]]

    # ── Error Handling ────────────────────────────────────────
    error: Optional[str]
    retry_count: int
    intermediate_steps: Annotated[Optional[List[Dict[str, Any]]], safe_append]

    # ── Progressive Complexity ────────────────────────────────
    complexity_index: int        
    total_pills: int            
