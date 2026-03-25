from typing import Any
from langgraph.graph import END, StateGraph, START
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.agents.output_assembler import output_assembler
from app.modules.pdf.flows.hybrid_ocr.agents.hybrid_ocr_agent import hybrid_ocr_retrieval_agent

def build_hybrid_ocr_graph(checkpointer: Any = None) -> Any:
    """Construct the Hybrid OCR analysis pipeline (PyMuPDF + Selective Gemini Flash)."""
    graph = StateGraph(AnalysisState)

    graph.add_node("hybrid_extraction", hybrid_ocr_retrieval_agent)
    graph.add_node("output_assembler", output_assembler)

    # Hybrid OCR Flow
    graph.add_edge(START, "hybrid_extraction")
    graph.add_edge("hybrid_extraction", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile(checkpointer=checkpointer)
