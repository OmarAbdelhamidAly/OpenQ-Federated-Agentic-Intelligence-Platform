"""SQL Pipeline — LangGraph StateGraph.

Wires the complete SQL pipeline:
  intake → [clarify?] → data_discovery → analysis
  → [retry?] → visualization → insight → recommendation → output_assembler → END

Note: No data cleaning step — SQL databases manage their own data integrity.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from app.agents.state import AnalysisState
from app.agents.intake_agent import intake_agent
from app.agents.output_assembler import output_assembler
from app.agents.sql.data_discovery_agent import data_discovery_agent
from app.agents.sql.analysis_agent import analysis_agent
from app.agents.sql.visualization_agent import visualization_agent
from app.agents.sql.insight_agent import insight_agent
from app.agents.sql.recommendation_agent import recommendation_agent


# ── Conditional Edge Functions ─────────────────────────────────────────────────

def needs_clarification(state: AnalysisState) -> Literal["clarify", "discover"]:
    """Route to clarification pause or continue to discovery."""
    if state.get("clarification_needed"):
        return "clarify"
    return "discover"


def should_retry(state: AnalysisState) -> Literal["retry", "visualize"]:
    """Route back to analysis on error (up to 3 retries)."""
    if state.get("error") and state.get("retry_count", 0) <= 3:
        return "retry"
    return "visualize"


# ── Build the Graph ────────────────────────────────────────────────────────────

def build_sql_graph() -> StateGraph:
    """Construct and compile the SQL LangGraph analysis pipeline.

    SQL-specific flow — no cleaning step (databases manage their own integrity).
    Goes directly from data_discovery → analysis.
    """
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("intake", intake_agent)
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("output_assembler", output_assembler)

    # Entry point
    graph.set_entry_point("intake")

    # intake → conditional: clarify or discover
    graph.add_conditional_edges(
        "intake",
        needs_clarification,
        {
            "clarify": END,       # Pause graph — wait for user clarification
            "discover": "data_discovery",
        },
    )

    # data_discovery → analysis (no cleaning step for SQL)
    graph.add_edge("data_discovery", "analysis")

    # analysis → conditional: retry or move to visualization
    graph.add_conditional_edges(
        "analysis",
        should_retry,
        {
            "retry": "analysis",
            "visualize": "visualization",
        },
    )

    # visualization → insight → recommendation → output_assembler → END
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "recommendation")
    graph.add_edge("recommendation", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile()


# Module-level compiled graph (singleton)
sql_pipeline = build_sql_graph()
