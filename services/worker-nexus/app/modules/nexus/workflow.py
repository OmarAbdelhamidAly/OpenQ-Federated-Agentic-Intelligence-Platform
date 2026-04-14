"""Strategic Nexus Workflow — Multi-source Orchestration."""
from langgraph.graph import StateGraph, END
from app.schemas.nexus_state import NexusState
import structlog

logger = structlog.get_logger(__name__)

def build_nexus_graph(checkpointer=None):
    """Build the autonomous orchestration graph."""
    from app.modules.nexus.agents.nexus_router import nexus_router
    from app.modules.nexus.agents.graph_explorer import graph_explorer
    from app.modules.nexus.agents.pillar_orchestrator import pillar_orchestrator
    from app.modules.nexus.agents.synthesis_engine import synthesis_engine
    from app.modules.nexus.agents.memory_manager_agent import memory_manager_agent
    from app.modules.nexus.agents.semantic_cache_agent import save_semantic_cache

    workflow = StateGraph(NexusState)

    # 1. Routing & Discovery
    workflow.add_node("router", nexus_router)
    workflow.add_node("explorer", graph_explorer)
    
    # 2. Specialist Execution
    workflow.add_node("orchestrator", pillar_orchestrator)
    
    # 3. Final Synthesis & Memory
    workflow.add_node("synthesizer", synthesis_engine)
    workflow.add_node("memory", memory_manager_agent)
    workflow.add_node("save_cache", save_semantic_cache)

    # Entry Point
    workflow.set_entry_point("router")

    # Edges
    workflow.add_conditional_edges(
        "router",
        lambda x: x["next_step"],
        {
            "explore": "explorer",
            "direct_query": "orchestrator",
            "finalize": "synthesizer"
        }
    )

    workflow.add_edge("explorer", "orchestrator")
    workflow.add_edge("orchestrator", "synthesizer")
    workflow.add_edge("synthesizer", "memory")
    workflow.add_edge("memory", "save_cache")
    workflow.add_edge("save_cache", END)

    return workflow.compile(checkpointer=checkpointer)
