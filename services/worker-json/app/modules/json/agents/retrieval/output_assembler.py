"""Output assembler — packages the final response from all agent outputs."""

from __future__ import annotations

from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState


async def output_assembler(state: AnalysisState) -> Dict[str, Any]:
    """Package all agent outputs into the final analysis response.

    This is the terminal node. It returns the complete state
    with all fields populated for storage in the database.
    """
    return {
        "chart_json": state.get("chart_json"),
        "viz_rationale": state.get("viz_rationale"),
        "chart_engine": state.get("chart_engine"),
        "insight_report": state.get("insight_report", ""),
        "executive_summary": state.get("executive_summary", ""),
        "recommendations": state.get("recommendations", []),
        "follow_up_suggestions": state.get("follow_up_suggestions", []),
        "generated_sql": state.get("generated_sql"),
        "intent": state.get("intent"),
        "relevant_columns": state.get("relevant_columns"),
        "error": state.get("error"),
    }
