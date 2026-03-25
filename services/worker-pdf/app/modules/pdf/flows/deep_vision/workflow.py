from typing import Any
from langgraph.graph import END, StateGraph, START
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.agents.output_assembler import output_assembler
from app.modules.pdf.flows.deep_vision.agents.pdf_agent import colpali_retrieval_agent

def build_deep_vision_graph(checkpointer: Any = None) -> Any:
    """Construct the Deep Vision PDF analysis pipeline (ColPali VLM)."""
    graph = StateGraph(AnalysisState)

    graph.add_node("retrieval", colpali_retrieval_agent)
    graph.add_node("output_assembler", output_assembler)

    # Deep Vision Flow
    graph.add_edge(START, "retrieval")
    graph.add_edge("retrieval", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile(checkpointer=checkpointer)
