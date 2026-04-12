"""SQL Pipeline — LangGraph StateGraph.

Wires the complete SQL pipeline:
  data_discovery → analysis → [reflection? retry on error]
  → visualization → insight → [verifier] → recommendation → output_assembler → END
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Union

from langgraph.graph import END, StateGraph, START

from app.domain.analysis.entities import AnalysisState
from app.modules.sql.agents.output_assembler import output_assembler
from app.modules.sql.agents.data_discovery_agent import data_discovery_agent
from app.modules.sql.agents.analysis_agent import analysis_agent
from app.modules.sql.agents.visualization_agent import visualization_agent
from app.modules.sql.agents.insight_agent import insight_agent
from app.modules.sql.agents.recommendation_agent import recommendation_agent
from app.modules.sql.agents.verifier_agent import verifier_agent
from app.modules.sql.agents.reflection_agent import reflection_agent
from app.modules.sql.agents.semantic_cache_agent import save_semantic_cache
from app.modules.sql.agents.memory_manager_agent import memory_manager_agent

from langgraph.checkpoint.redis import AsyncRedisSaver
import redis.asyncio as redis
from app.infrastructure.config import settings

# ── Nodes ──────────────────────────────────────────────────────────────────────

async def human_approval_node(state: AnalysisState) -> Dict[str, Any]:
    """Waiting node for Human-in-the-loop approval."""
    return {"error": None}


async def sql_execution_node(state: AnalysisState) -> Dict[str, Any]:
    """Actually run the approved SQL query and fetch full results."""
    import structlog
    _exec_logger = structlog.get_logger("sql.execution_node")

    from app.modules.sql.tools.run_sql_query import run_sql_query
    from app.modules.sql.tools.load_data_source import get_connection_string

    try:
        connection_string = get_connection_string(state)
    except FileNotFoundError as e:
        _exec_logger.error("sqlite_file_not_found", file_path=state.get("file_path"), error=str(e))
        return {"error": f"Database file not found: {e}"}

    query = state.get("generated_sql")
    params = state.get("analysis_results", {}).get("plan", {}).get("params", {})

    if not query:
        return {"error": "No SQL query found to execute."}

    _exec_logger.info("sql_execution_start", query=query, params=params)

    try:
        result = await run_sql_query.ainvoke({
            "connection_string": connection_string,
            "query": query,
            "params": params,
            "limit": 1000,
        })

        row_count = result.get("row_count", 0)
        _exec_logger.info("sql_execution_done", row_count=row_count)

        # ── Trigger Reflection if 0 rows returned ──
        if row_count == 0:
            return {
                "analysis_results": {**(state.get("analysis_results") or {}), **result},
                "reflection_context": "Query returned 0 rows. Verify table/column names and case-sensitivity.",
                "error": None,
            }

        return {
            "analysis_results": {**(state.get("analysis_results") or {}), **result},
            "error": None,
        }
    except Exception as e:
        _exec_logger.error("sql_execution_failed", error=str(e), query=query)
        return {"error": str(e)}


async def verifier_node(state: AnalysisState) -> Dict[str, Any]:
    """Wraps the Verifier Agent specifically for the LangGraph workflow."""
    return await verifier_agent(state)


async def hybrid_fusion_node(state: AnalysisState) -> Dict[str, Any]:
    """Retrieves unstructured KB context related to the SQL results."""
    from app.modules.sql.utils.retrieval import get_kb_context
    question = state.get("question", "")
    kb_id = state.get("kb_id")
    kb_context = await get_kb_context(kb_id, question)
    return {
        "analysis_results": {
            **(state.get("analysis_results") or {}),
            "kb_context": kb_context
        }
    }


# ── Build the Graph ────────────────────────────────────────────────────────────

def build_sql_graph(checkpointer: Any = None) -> Any:
    """Construct and compile the SQL LangGraph analysis pipeline."""
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("analysis_generator", analysis_agent)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("reflection", reflection_agent)
    graph.add_node("execution", sql_execution_node)
    graph.add_node("hybrid_fusion", hybrid_fusion_node)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("verifier", verifier_node)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("save_cache", save_semantic_cache)
    graph.add_node("memory", memory_manager_agent)
    graph.add_node("output_assembler", output_assembler)

    # Setup Routing Logic
    graph.add_edge(START, "data_discovery")
    graph.add_edge("data_discovery", "analysis_generator")

    def route_after_generator(state: AnalysisState) -> str:
        if state.get("error"):
            if state.get("retry_count", 0) < 3:
                return "reflection"
            return "__end__"
        if state.get("user_id") == "auto_analysis" or state.get("approval_granted"):
            return "execution"
        return "human_approval"

    graph.add_conditional_edges(
        "analysis_generator",
        route_after_generator,
        {
            "human_approval": "human_approval",
            "execution": "execution",
            "reflection": "reflection",
            "__end__": END
        }
    )

    graph.add_edge("human_approval", "execution")

    def route_after_execution(state: AnalysisState) -> Literal["reflection", "hybrid_fusion"]:
        # Only retry via reflection if we haven't exceeded max retries.
        # Without this check, reflection → execution → reflection creates an infinite loop.
        has_issue = state.get("error") or state.get("reflection_context")
        under_retry_limit = state.get("retry_count", 0) < 3
        if has_issue and under_retry_limit:
            return "reflection"
        return "hybrid_fusion"

    graph.add_conditional_edges(
        "execution",
        route_after_execution,
        {
            "reflection": "reflection",
            "hybrid_fusion": "hybrid_fusion",
        }
    )

    # After reflection fixes the SQL, re-execute it directly.
    # Do NOT loop back to analysis_generator — that would re-run the LLM
    # from scratch and risk it generating a simpler fallback query.
    graph.add_edge("reflection", "execution")
    graph.add_edge("hybrid_fusion", "visualization")
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "verifier")
    graph.add_edge("verifier", "recommendation")
    graph.add_edge("recommendation", "save_cache")
    graph.add_edge("save_cache", "memory")
    graph.add_edge("memory", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile(checkpointer=checkpointer, interrupt_after=["human_approval"])
