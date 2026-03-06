"""SQL Pipeline — LangGraph StateGraph.

Wires the complete SQL pipeline:
  intake → [clarify?] → data_discovery → analysis
  → [retry?] → visualization → insight → recommendation → output_assembler → END

Note: No data cleaning step — SQL databases manage their own data integrity.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from app.domain.analysis.entities import AnalysisState
from app.modules.shared.agents.intake_agent import intake_agent
from app.modules.shared.agents.output_assembler import output_assembler
from app.modules.sql.agents.data_discovery_agent import data_discovery_agent
from app.modules.sql.agents.analysis_agent import analysis_agent
from app.modules.sql.agents.visualization_agent import visualization_agent
from app.modules.sql.agents.insight_agent import insight_agent
from app.modules.sql.agents.recommendation_agent import recommendation_agent
from app.modules.shared.agents.guardrail_agent import guardrail_agent


from langgraph.checkpoint.memory import MemorySaver

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
    if (state.get("error") or state.get("policy_violation")) and state.get("retry_count", 0) <= 3:
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
    from app.modules.sql.tools.run_sql_query import run_sql_query
    from app.modules.shared.tools.load_data_source import get_connection_string
    
    connection_string = get_connection_string(state)
    query = state.get("generated_sql")
    params = state.get("analysis_results", {}).get("plan", {}).get("params", {})
    
    if not query:
        return {"error": "No SQL query found to execute."}
        
    try:
        result = run_sql_query.invoke({
            "connection_string": connection_string,
            "query": query,
            "params": params,
            "limit": 1000,
        })
        return {
            "analysis_results": {
                **state.get("analysis_results", {}),
                **result,
            },
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}


# ── Build the Graph ────────────────────────────────────────────────────────────

def build_sql_graph() -> StateGraph:
    """Construct and compile the SQL LangGraph analysis pipeline."""
    from langgraph.graph import START
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("intake", intake_agent)
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("analysis_generator", analysis_agent) # ReAct phase
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("guardrail", guardrail_agent)
    graph.add_node("execution", sql_execution_node)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("output_assembler", output_assembler)

    # 1. True Parallel Start: Both trigger on START
    graph.add_edge(START, "intake")
    graph.add_edge(START, "data_discovery")
    
    # 2. Joins at generator
    graph.add_edge("data_discovery", "analysis_generator")
    
    def check_intake_and_proceed(state: AnalysisState) -> Literal["clarify", "analysis_generator"]:
        if state.get("clarification_needed"):
            return "clarify"
        return "analysis_generator"

    graph.add_conditional_edges(
        "intake",
        check_intake_and_proceed,
        {
            "clarify": END,
            "analysis_generator": "analysis_generator"
        }
    )

    # 3. Analysis (ReAct) -> Approval Pause OR Fast-track for auto-analysis
    def route_after_generator(state: AnalysisState) -> Literal["human_approval", "guardrail"]:
        # Auto-analysis runs in the background, no human to approve
        if state.get("user_id") == "auto_analysis":
            return "guardrail"
        return "human_approval"

    graph.add_conditional_edges(
        "analysis_generator",
        route_after_generator,
        {
            "human_approval": "human_approval",
            "guardrail": "guardrail"
        }
    )

    # 4. Post-Approval: Guardrail -> Execution
    graph.add_edge("human_approval", "guardrail")
    
    def route_post_guardrail(state: AnalysisState) -> Literal["retry", "execute"]:
        if state.get("policy_violation") and state.get("retry_count", 0) <= 2:
            return "retry"
        return "execute"

    graph.add_conditional_edges(
        "guardrail",
        route_post_guardrail,
        {
            "retry": "analysis_generator",
            "execute": "execution",
        },
    )

    # 5. Execution -> Output chain
    graph.add_edge("execution", "visualization")
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "recommendation")
    graph.add_edge("recommendation", "output_assembler")
    graph.add_edge("output_assembler", END)

    # Enable memory (checkpointer)
    memory = MemorySaver()
    # Interrupt at human_approval to show generated_sql to user
    return graph.compile(checkpointer=memory, interrupt_before=["human_approval"])


# Module-level compiled graph (singleton)
sql_pipeline = build_sql_graph()
