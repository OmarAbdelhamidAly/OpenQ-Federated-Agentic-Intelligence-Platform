from typing import Any
from langgraph.graph import END, StateGraph, START
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.agents.output_assembler import output_assembler
from app.modules.pdf.flows.fast_text.agents.fast_text_agent import fast_text_retrieval_agent

def build_fast_text_graph(checkpointer: Any = None) -> Any:
    """Construct the Fast Text PDF analysis pipeline (HNSW + FastEmbed + CrossEncoder)."""
    graph = StateGraph(AnalysisState)

    graph.add_node("retrieval", fast_text_retrieval_agent)
    graph.add_node("output_assembler", output_assembler)

    # Fast Text Flow
    graph.add_edge(START, "retrieval")
    graph.add_edge("retrieval", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile(checkpointer=checkpointer)
