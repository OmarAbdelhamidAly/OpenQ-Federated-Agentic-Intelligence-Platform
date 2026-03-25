"""CSV Pipeline — LangGraph StateGraph.

Wires the complete CSV pipeline:
  intake → [clarify?] → data_discovery → [clean?] → analysis
  → [retry?] → visualization → insight → recommendation → output_assembler → END
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from langgraph.checkpoint.redis import AsyncRedisSaver
import redis.asyncio as redis
from app.infrastructure.config import settings
from app.domain.analysis.entities import AnalysisState
from app.modules.csv.agents.output_assembler import output_assembler
from app.modules.csv.agents.data_discovery_agent import data_discovery_agent
from app.modules.csv.agents.data_cleaning_agent import data_cleaning_agent
from app.modules.csv.agents.analysis_agent import analysis_agent
from app.modules.csv.agents.visualization_agent import visualization_agent
from app.modules.csv.agents.insight_agent import insight_agent
from app.modules.csv.agents.recommendation_agent import recommendation_agent

from app.modules.csv.agents.reflection_agent import reflection_agent
from app.modules.csv.agents.guardrail_agent import guardrail_agent
from app.modules.csv.agents.semantic_cache_agent import save_semantic_cache


# ── Conditional Edge Functions ─────────────────────────────────────────────────

# Governance has been moved to a separate microservice layer.


def needs_cleaning(state: AnalysisState) -> Literal["clean", "analyze"]:
    """Route to cleaning if data quality is below 0.9."""
    quality = state.get("data_quality_score", 1.0)
    if quality < 0.9:
        return "clean"
    return "analyze"


def check_analysis_result(state: AnalysisState) -> Literal["reflection", "visualize"]:
    """Route to reflection on error or empty results (up to 3 retries)."""
    error = state.get("error")
    retry_count = state.get("retry_count", 0)
    
    # If there's an error and we haven't exceeded retries, reflect and repair
    if error and retry_count < 3:
        return "reflection"
    
    # Otherwise, proceed to visualization (which handles its own error display)
    return "visualize"


# ── Build the Graph ────────────────────────────────────────────────────────────

def build_csv_graph(checkpointer: Any = None) -> Any:
    """Construct and compile the CSV LangGraph analysis pipeline.

    CSV-specific flow includes a data cleaning step (skipped for SQL).
    """
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("data_cleaning", data_cleaning_agent)
    graph.add_node("guardrail", guardrail_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("reflection", reflection_agent)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("output_assembler", output_assembler)
    graph.add_node("save_cache", save_semantic_cache)

    # Entry point is Discovery
    graph.set_entry_point("data_discovery")

    # Logic moved to governance layer

    # data_discovery → conditional: clean or analyze
    graph.add_conditional_edges(
        "data_discovery",
        needs_cleaning,
        {
            "clean": "data_cleaning",
            "analyze": "guardrail",
        },
    )

    # data_cleaning → guardrail → analysis
    graph.add_edge("data_cleaning", "guardrail")
    graph.add_edge("guardrail", "analysis")

    # analysis → conditional: reflection or visualization
    graph.add_conditional_edges(
        "analysis",
        check_analysis_result,
        {
            "reflection": "reflection",
            "visualize": "visualization",
        }
    )

    # reflection → analysis (retry loop)
    graph.add_edge("reflection", "analysis")

    # visualization → insight → recommendation → output_assembler → END
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "recommendation")
    graph.add_edge("recommendation", "output_assembler")
    graph.add_edge("output_assembler", "save_cache")
    graph.add_edge("save_cache", END)

    return graph.compile(checkpointer=checkpointer)
