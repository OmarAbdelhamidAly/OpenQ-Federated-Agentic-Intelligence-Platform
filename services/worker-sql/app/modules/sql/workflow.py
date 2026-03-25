"""SQL Pipeline — LangGraph StateGraph.

Wires the complete SQL pipeline:
  intake → [clarify?] → data_discovery → analysis
  → [retry?] → visualization → insight → recommendation → output_assembler → END

Note: No data cleaning step — SQL databases manage their own data integrity.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Union

from langgraph.graph import END, StateGraph

from app.domain.analysis.entities import AnalysisState
from app.modules.sql.agents.output_assembler import output_assembler
from app.modules.sql.agents.data_discovery_agent import data_discovery_agent
from app.modules.sql.agents.analysis_agent import analysis_agent
from app.modules.sql.agents.visualization_agent import visualization_agent
from app.modules.sql.agents.insight_agent import insight_agent
from app.modules.sql.agents.recommendation_agent import recommendation_agent


from langgraph.checkpoint.redis import AsyncRedisSaver
import redis.asyncio as redis
from app.infrastructure.config import settings

# ── Conditional Edge Functions ─────────────────────────────────────────────────

def route_after_intake(state: AnalysisState) -> Literal["clarify", "analysis_prep"]:
    """Route to clarification if needed, otherwise prepare for analysis."""
    if state.get("clarification_needed"):
        return "clarify"
    return "analysis_prep"


def should_approve(state: AnalysisState) -> Literal["approve", "analyze"]:
    """Route to human approval if sensitive or explicitly requested."""
    # Simplified logic: Always require approval for now as per user request (HITL)
    return "approve"


def should_retry(state: AnalysisState) -> Literal["retry", "visualize"]:
    """Route back to analysis on error or policy violation (up to 3 retries)."""
    if (state.get("error") or state.get("policy_violation")) and state.get("retry_count", 0) < 2:
        return "retry"
    return "visualize"


# ── Nodes ──────────────────────────────────────────────────────────────────────

# ── Nodes ──────────────────────────────────────────────────────────────────────

async def human_approval_node(state: AnalysisState) -> Dict[str, Any]:
    """Waiting node for Human-in-the-loop approval."""
    # This node is where the graph interrupts.
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
        # SQLite file not found — surface a clear, actionable error.
        # Without this check, SQLite silently creates an empty DB and
        # returns 0 rows with no error at all.
        _exec_logger.error(
            "sqlite_file_not_found",
            file_path=state.get("file_path"),
            error=str(e),
        )
        return {"error": f"Database file not found: {e}"}

    query = state.get("generated_sql")
    params = state.get("analysis_results", {}).get("plan", {}).get("params", {})

    if not query:
        return {"error": "No SQL query found to execute."}

    # Log exactly what we are about to run so the cause of 0-row results is
    # visible in the worker logs without having to guess.
    _exec_logger.info(
        "sql_execution_start",
        query=query,
        params=params,
        # Mask credentials but keep the driver+host for debugging
        connection_hint=(connection_string or "")[:80],
    )

    try:
        result = await run_sql_query.ainvoke({
            "connection_string": connection_string,
            "query": query,
            "params": params,
            "limit": 1000,
        })

        row_count = result.get("row_count", 0)
        _exec_logger.info("sql_execution_done", row_count=row_count)

        # ── Self-Reflection Trigger ──
        # If 0 rows are found, build a hint and send the job back to the
        # analysis_generator via backtrack so it can try a better query.
        reflection_count = state.get("reflection_count", 0)
        if row_count == 0 and reflection_count < 1:
            hint = (
                f"The query executed successfully but returned 0 rows. "
                f"The SQL that was run was: [{query}]. "
                "Check that table names, column names, and any string literal "
                "values exactly match what is in the database."
            )

            # Extra hint: case-mismatch in WHERE clause literals
            schema = state.get("schema_summary", {})
            if schema:
                literals = re.findall(r"=\s*'(.*?)'", query)
                for lit in literals:
                    for table in schema.get("tables", []):
                        for col in table.get("columns", []):
                            enums = col.get("low_cardinality_values", [])
                            if any(e.lower() == lit.lower() and e != lit for e in enums):
                                matching_enum = next(e for e in enums if e.lower() == lit.lower())
                                hint += (
                                    f" Hint: You filtered by '{lit}', but sampled data "
                                    f"for '{table['table']}.{col['name']}' shows values "
                                    f"like '{matching_enum}'. SQL is case-sensitive."
                                )

            _exec_logger.warning("sql_returned_zero_rows", hint=hint)
            return {
                "analysis_results": {
                    **(state.get("analysis_results") or {}),
                    **result,
                },
                "reflection_context": hint,
                "reflection_count": reflection_count + 1,
                "error": None,
            }

        return {
            "analysis_results": {
                **(state.get("analysis_results") or {}),
                **result,
                "reflection_count": state.get("reflection_count", 0),
            },
            "reflection_context": None,
            "error": None,
        }
    except Exception as e:
        _exec_logger.error("sql_execution_failed", error=str(e), query=query)
        return {"error": str(e)}


async def backtrack_node(state: AnalysisState) -> Dict[str, Any]:
    """Analyzes failure and suggests a strategic pivot to the generator (Idea 11)."""
    retry_count = state.get("retry_count", 0)
    error = state.get("error") or state.get("policy_violation")
    
    # Heuristic: If we've retried and still fail, suggest a simplified schema
    hint = f"\n[BACKTRACK] Previous attempt failed with: {error}. "
    if "violation" in str(error).lower():
        hint += "Try a less sensitive query or explain why this data is needed."
    else:
        hint += "Try simplifying the JOIN logic or checking column names using the tool again."
        
    return {
        "retry_count": retry_count + 1,
        "reflection_context": (state.get("reflection_context") or "") + hint,
        "error": None,
        "policy_violation": None
    }


async def verifier_node(state: AnalysisState) -> Dict[str, Any]:
    """Wraps the Verifier Agent specifically for the LangGraph workflow (Idea 9)."""
    from app.modules.sql.agents.verifier_agent import verifier_agent
    return await verifier_agent(state)


async def memory_persistence_node(state: AnalysisState) -> Dict[str, Any]:
    """Saves successful analyses to long-term memory (Idea 16)."""
    from app.modules.sql.utils.insight_memory import insight_memory
    
    analysis = state.get("analysis_results", {})
    insight = state.get("insight_report", "")
    question = state.get("question", "")
    
    if insight and analysis.get("plan"):
        insight_memory.save_analysis(
            question=question,
            sql=analysis["plan"].get("query"),
            insight=insight
        )
    return {}


async def hybrid_fusion_node(state: AnalysisState) -> Dict[str, Any]:
    """Retrieves unstructured KB context related to the SQL results (Idea 13)."""
    from app.modules.sql.utils.retrieval import get_kb_context
    
    question = state.get("question", "")
    kb_id = state.get("kb_id")
    sql_results = state.get("analysis_results", {}).get("data", [])
    
    # 1. Fetch context based on original question
    kb_context = await get_kb_context(kb_id, question)
    
    # 2. Logic to refine search based on SQL results could go here
    # For now, we just pass the KB context forward
    return {
        "analysis_results": {
            **(state.get("analysis_results") or {}),
            "kb_context": kb_context
        }
    }


# ── Build the Graph ────────────────────────────────────────────────────────────

def build_sql_graph(checkpointer: Any = None) -> Any:
    """Construct and compile the SQL LangGraph analysis pipeline."""
    from langgraph.graph import START
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("analysis_generator", analysis_agent)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("backtrack", backtrack_node)
    graph.add_node("execution", sql_execution_node)
    graph.add_node("hybrid_fusion", hybrid_fusion_node)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("verifier", verifier_node)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("memory_persistence", memory_persistence_node)
    graph.add_node("output_assembler", output_assembler)

    # 1. Start at Discovery
    graph.add_edge(START, "data_discovery")
    graph.add_edge("data_discovery", "analysis_generator")

    # 3. Analysis (ReAct) -> Approval Pause OR Fast-track for auto-analysis
    def route_after_generator(state: AnalysisState) -> str:
        if state.get("error"):
            if state.get("retry_count", 0) < 3:
                return "backtrack"
            return "__end__"
            
        # Auto-analysis runs in the background, no human to approve
        if state.get("user_id") == "auto_analysis" or state.get("approval_granted"):
            return "execution"
        return "human_approval"

    graph.add_conditional_edges(
        "analysis_generator",
        route_after_generator,
        {
            "human_approval": "human_approval",
            "execution": "execution",
            "backtrack": "backtrack",
            "__end__": END
        }
    )

    # 3. Post-Approval logic
    graph.add_edge("human_approval", "execution")

    # 5. Execution -> Reflection OR Visualization + Fusion
    def route_after_execution(state: AnalysisState) -> Literal["backtrack", "hybrid_fusion"]:
        if state.get("reflection_context"):
            return "backtrack"
        return "hybrid_fusion"

    graph.add_conditional_edges(
        "execution",
        route_after_execution,
        {
            "backtrack": "backtrack",
            "visualization": "visualization",
            "hybrid_fusion": "hybrid_fusion",
        }
    )

    # 6. Sequential progression (Idea: linearize for state stability)
    graph.add_edge("backtrack", "analysis_generator")
    graph.add_edge("hybrid_fusion", "visualization")
    graph.add_edge("visualization", "insight")
    
    # 7. Quality Control Chain (Idea 9 & 16)
    graph.add_edge("insight", "verifier")
    
    def route_after_verifier(state: AnalysisState) -> Union[str, List[str]]:
        # For now, always proceed to recommendation, but save to memory if verified
        return "recommendation"

    graph.add_edge("verifier", "recommendation")
    graph.add_edge("recommendation", "memory_persistence")
    graph.add_edge("memory_persistence", "output_assembler")
    graph.add_edge("output_assembler", END)

    # Interrupt at human_approval to show generated_sql to user
    return graph.compile(checkpointer=checkpointer, interrupt_after=["human_approval"])
