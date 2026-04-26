"""
OpenQ Nexus LangGraph Orchestration
The internal implementation of the nodes is strictly decoupled in the `nodes/` package.
This file purely builds and compiles the workflow.
"""
from langgraph.graph import StateGraph, END
from app.schemas.nexus_state import NexusState

from app.modules.retrieval.nodes import (
    query_fusion_node,
    gather_context_node,
    rerank_context_node,
    synthesis_node
)

def create_nexus_graph():
    """Build and compile the LangGraph orchestration pipeline."""
    workflow = StateGraph(NexusState)

    workflow.add_node("query_fusion",    query_fusion_node)
    workflow.add_node("gather_context",  gather_context_node)
    workflow.add_node("rerank_context",  rerank_context_node)
    workflow.add_node("synthesis_layer", synthesis_node)

    workflow.set_entry_point("query_fusion")
    workflow.add_edge("query_fusion",    "gather_context")
    workflow.add_edge("gather_context",  "rerank_context")
    workflow.add_edge("rerank_context",  "synthesis_layer")
    workflow.add_edge("synthesis_layer", END)

    return workflow.compile()