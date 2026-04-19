import structlog
from typing import Any, Dict, List, Literal, Union
from langgraph.graph import END, StateGraph, START

from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.agents.retrieval.query_refiner import query_refiner_agent
from app.modules.pdf.agents.retrieval.router_agent import router_agent
from app.modules.pdf.agents.retrieval.chat_agent import chat_agent
from app.modules.pdf.agents.retrieval.retrieval_agent import adaptive_retrieval_agent
from app.modules.pdf.agents.retrieval.verifier_agent import verifier_agent
from app.modules.pdf.agents.retrieval.analyst_agent import analyst_agent
from app.modules.pdf.agents.retrieval.evaluation_agent import evaluation_agent
from app.modules.pdf.agents.retrieval.memory_manager_agent import memory_manager_agent
from app.modules.pdf.agents.retrieval.semantic_cache_agent import save_semantic_cache
from app.modules.pdf.agents.retrieval.output_assembler import output_assembler

# Import existing flow agents
from app.modules.pdf.agents.indexing.deep_vision.agents.pdf_agent import colpali_retrieval_agent as vision_synthesis
from app.modules.pdf.agents.indexing.fast_text.agents.fast_text_agent import fast_text_retrieval_agent as text_synthesis
from app.modules.pdf.agents.indexing.hybrid_ocr.agents.hybrid_ocr_agent import hybrid_ocr_retrieval_agent as ocr_synthesis

logger = structlog.get_logger(__name__)

# ── Conditional Routing ──────────────────────────────────────────────────────

def route_after_router(state: AnalysisState) -> Literal["chat", "retrieval"]:
    """Routes to direct chat or document retrieval."""
    if state.get("route") == "greeting":
        return "chat"
    return "retrieval"

def route_after_retrieval(state: AnalysisState) -> Literal["refine", "vision", "text", "ocr"]:
    """Reflection loop: If retrieval fails, refinement is needed. Otherwise, pick synthesis mode."""
    if state.get("reflection_needed"):
        return "refine"
    
    mode = state.get("analysis_mode", "deep_vision")
    if mode == "fast_text": return "text"
    if mode == "hybrid": return "ocr"
    return "vision"

def route_after_verifier(state: AnalysisState) -> Literal["finalize", "vision", "text", "ocr"]:
    """Anti-Hallucination loop: If verification fails, retry synthesis."""
    if state.get("verified") is False and state.get("retry_count", 0) < 2:
        mode = state.get("analysis_mode", "deep_vision")
        if mode == "fast_text": return "text"
        if mode == "hybrid": return "ocr"
        return "vision"
    return "finalize"

# ── Graph Construction ───────────────────────────────────────────────────────

def build_pdf_graph(checkpointer: Any = None, mode: str = "deep_vision") -> Any:
    """The Master PDF Orchestrator — unifying all flows with AI reasoning."""
    graph = StateGraph(AnalysisState)

    # 1. Add Nodes
    graph.add_node("refine", query_refiner_agent)
    graph.add_node("router", router_agent)
    graph.add_node("chat", chat_agent)
    graph.add_node("retrieval", adaptive_retrieval_agent)
    
    # Synthesis Engines
    graph.add_node("vision_synthesis", vision_synthesis)
    graph.add_node("text_synthesis", text_synthesis)
    graph.add_node("ocr_synthesis", ocr_synthesis)
    
    graph.add_node("verifier", verifier_agent)
    graph.add_node("analyst", analyst_agent)
    graph.add_node("evaluator", evaluation_agent)
    graph.add_node("memory", memory_manager_agent)
    graph.add_node("save_cache", save_semantic_cache)
    graph.add_node("output_assembler", output_assembler)

    # 2. Define Edges
    graph.add_edge(START, "refine")
    graph.add_edge("refine", "router")
    
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "chat": "chat",
            "retrieval": "retrieval"
        }
    )
    
    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "refine": "refine",
            "vision": "vision_synthesis",
            "text": "text_synthesis",
            "ocr": "ocr_synthesis"
        }
    )
    
    graph.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "vision": "vision_synthesis",
            "text": "text_synthesis",
            "ocr": "ocr_synthesis",
            "finalize": "analyst"
        }
    )
    
    graph.add_edge("vision_synthesis", "verifier")
    graph.add_edge("text_synthesis", "verifier")
    graph.add_edge("ocr_synthesis", "verifier")
    
    graph.add_edge("chat", "memory")
    graph.add_edge("analyst", "evaluator")
    graph.add_edge("evaluator", "memory")
    graph.add_edge("memory", "save_cache")
    graph.add_edge("save_cache", "output_assembler")
    graph.add_edge("output_assembler", END)

    # Compile the graph without interrupt to allow full deep vision RAG analysis
    return graph.compile(checkpointer=checkpointer)
