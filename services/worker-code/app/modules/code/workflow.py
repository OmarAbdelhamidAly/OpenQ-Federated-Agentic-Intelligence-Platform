import structlog
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

from app.domain.analysis.entities import CodeAnalysisState
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.modules.code.agents.data_discovery_agent import data_discovery_agent
from app.modules.code.agents.cypher_generator_agent import cypher_generator_agent
from app.modules.code.agents.reflection_agent import reflection_agent
from app.modules.code.agents.insight_agent import insight_agent
from app.modules.code.agents.memory_manager_agent import memory_manager_agent
from app.modules.code.agents.semantic_cache_agent import save_semantic_cache
from app.modules.code.agents.output_assembler import output_assembler

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 3


async def cypher_execution_node(state: CodeAnalysisState) -> Dict[str, Any]:
    """
    Execute the generated Cypher query against Neo4j and store results.

    Uses the module-level singleton driver via Neo4jAdapter — no new
    TCP connections are created per request.
    """
    source_id = state.get("source_id")
    query     = state.get("cypher_query")
    params    = state.get("cypher_params") or {}

    logger.info("cypher_execution_started", source_id=source_id)

    if not query:
        return {"error": "No Cypher query to execute", "execution_results": []}

    adapter = Neo4jAdapter()  # borrows from the shared pool singleton
    try:
        results = await adapter.execute_cypher(query, params)
        logger.info(
            "cypher_execution_finished",
            source_id=source_id,
            row_count=len(results),
        )
        return {"execution_results": results, "error": None}

    except Exception as exc:
        logger.error("cypher_execution_failed", source_id=source_id, error=str(exc))
        return {"error": str(exc), "execution_results": []}


def build_code_workflow(checkpointer: Any = None) -> Any:
    """
    Assemble the LangGraph state machine for codebase Q&A.

    Flow
    ----
    START
      → discovery      (build schema description with live stats)
      → generator      (LLM: question → Cypher)
        ↓ error & retries < MAX  → reflection → generator  (retry loop)
        ↓ error & retries >= MAX → END
        ↓ no error
      → execution      (run Cypher on Neo4j)
        ↓ error & retries < MAX  → reflection → generator
        ↓ no error
      → insight        (LLM: results + code snippets → narrative)
      → memory         (memory manager: slide window and sum)
      → assembler      (package final payload)
      → END
    """
    graph = StateGraph(CodeAnalysisState)

    graph.add_node("discovery",  data_discovery_agent)
    graph.add_node("generator",  cypher_generator_agent)
    graph.add_node("reflection", reflection_agent)
    graph.add_node("execution",  cypher_execution_node)
    graph.add_node("insight",    insight_agent)
    graph.add_node("memory",     memory_manager_agent)
    graph.add_node("save_cache", save_semantic_cache)
    graph.add_node("assembler",  output_assembler)

    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "generator")

    # ── After generator ───────────────────────────────────────────────
    def route_after_generator(
        state: CodeAnalysisState,
    ) -> Literal["reflection", "execution", "__end__"]:
        if state.get("error"):
            return "reflection" if state.get("retry_count", 0) < _MAX_RETRIES else "__end__"
        return "execution"

    graph.add_conditional_edges("generator", route_after_generator)

    # ── After execution ───────────────────────────────────────────────
    def route_after_execution(
        state: CodeAnalysisState,
    ) -> Literal["reflection", "insight"]:
        if state.get("error") and state.get("retry_count", 0) < _MAX_RETRIES:
            return "reflection"
        return "insight"

    graph.add_conditional_edges("execution", route_after_execution)

    graph.add_edge("reflection", "generator")
    graph.add_edge("insight",    "memory")
    graph.add_edge("memory",     "save_cache")
    graph.add_edge("save_cache", "assembler")
    graph.add_edge("assembler",  END)

    return graph.compile(checkpointer=checkpointer)
