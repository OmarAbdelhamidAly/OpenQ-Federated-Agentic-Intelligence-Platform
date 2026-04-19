"""JSON Pipeline — LangGraph StateGraph.

Wires the complete JSON pipeline backed by MongoDB:
  data_discovery → guardrail → analysis → [reflection? retry on error]
  → visualization → insight → [verifier] → recommendation → output_assembler → END
"""

from typing import Any, Literal
from langgraph.graph import END, StateGraph, START

from app.domain.analysis.entities import AnalysisState
from app.modules.json.agents.retrieval.output_assembler import output_assembler
from app.modules.json.agents.retrieval.data_discovery_agent import data_discovery_agent
from app.modules.json.agents.retrieval.guardrail_agent import guardrail_agent
from app.modules.json.agents.retrieval.analysis_agent import analysis_agent
from app.modules.json.agents.retrieval.reflection_agent import reflection_agent
from app.modules.json.agents.retrieval.visualization_agent import visualization_agent
from app.modules.json.agents.retrieval.insight_agent import insight_agent
from app.modules.json.agents.retrieval.verifier_agent import verifier_agent
from app.modules.json.agents.retrieval.recommendation_agent import recommendation_agent
from app.modules.json.agents.retrieval.semantic_cache_agent import save_semantic_cache

def check_analysis_result(state: AnalysisState) -> Literal["reflection", "visualize"]:
    """Route to reflection on error (up to 3 retries)."""
    error = state.get("error")
    retry_count = state.get("retry_count", 0)
    
    if error and retry_count < 3:
        return "reflection"
    
    return "visualize"

def build_json_graph(checkpointer: Any = None) -> Any:
    """Construct a JSON analysis pipeline with MongoDB and self-reflection."""
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("data_discovery", data_discovery_agent)
    graph.add_node("guardrail", guardrail_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("reflection", reflection_agent)
    graph.add_node("visualization", visualization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("verifier", verifier_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("output_assembler", output_assembler)
    graph.add_node("save_cache", save_semantic_cache)

    # Setup flow
    graph.set_entry_point("data_discovery")
    
    graph.add_edge("data_discovery", "guardrail")
    graph.add_edge("guardrail", "analysis")
    
    graph.add_conditional_edges(
        "analysis",
        check_analysis_result,
        {
            "reflection": "reflection",
            "visualize": "visualization",
        }
    )
    
    graph.add_edge("reflection", "analysis")
    
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "verifier")
    graph.add_edge("verifier", "recommendation")
    graph.add_edge("recommendation", "output_assembler")
    graph.add_edge("output_assembler", "save_cache")
    graph.add_edge("save_cache", END)

    return graph.compile(checkpointer=checkpointer)
