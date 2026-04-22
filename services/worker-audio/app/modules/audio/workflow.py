"""Audio Intelligence LangGraph Workflow — 9-Node Pipeline.

Flow:
  START
    → audio_profiler      (validate + metadata)
    → preprocessor        (normalize + base64)
    → transcription       (gemini-2.5-flash-preview, audio input)
    → diarization         (resolve speaker identities)
    → entity_extractor    (llama-3.1-8b, text only)
    → summarizer          (gemini-flash-lite, text only)
    → evaluator           (local SLMs, zero-cost)
    → [vector_indexer ║ graph_knowledge_builder]  (parallel — both independent)
    → semantic_cache      (save result to Qdrant cache)
    → output_assembler
  END
"""
from __future__ import annotations
from typing import Any, Literal
import structlog
from langgraph.graph import END, StateGraph, START

from app.domain.analysis.entities import AudioAnalysisState
from app.modules.audio.agents.indexing.audio_profiler import audio_profiler_agent
from app.modules.audio.agents.indexing.preprocessor_agent import preprocessor_agent
from app.modules.audio.agents.indexing.transcription_agent import transcription_agent
from app.modules.audio.agents.indexing.diarization_agent import diarization_agent
from app.modules.audio.agents.indexing.entity_extractor import entity_extractor_agent
from app.modules.audio.agents.indexing.summarizer_agent import summarizer_agent
from app.modules.audio.agents.indexing.evaluation_agent import evaluation_agent
from app.modules.audio.agents.indexing.vector_indexer import vector_indexer_agent
from app.modules.audio.agents.indexing.graph_knowledge_builder import graph_knowledge_builder_agent
from app.modules.audio.agents.indexing.output_assembler import output_assembler
from app.modules.audio.agents.retrieval.semantic_cache_agent import save_semantic_cache

logger = structlog.get_logger(__name__)


# ── Conditional Routing ───────────────────────────────────────────────────────

def route_after_profiler(state: AudioAnalysisState) -> Literal["preprocess", "end"]:
    """Abort pipeline immediately on fatal profiler errors."""
    if state.get("error"):
        return "end"
    return "preprocess"


def route_after_transcription(state: AudioAnalysisState) -> Literal["diarize", "end"]:
    """Skip diarization if transcription failed."""
    if state.get("error") or not state.get("raw_transcript"):
        return "end"
    return "diarize"


# ── Graph Construction ────────────────────────────────────────────────────────

def build_audio_graph(checkpointer: Any = None) -> Any:
    """Build and compile the Audio Intelligence LangGraph pipeline."""
    graph = StateGraph(AudioAnalysisState)

    # ── Register Nodes ────────────────────────────────────────────────────────
    graph.add_node("audio_profiler", audio_profiler_agent)
    graph.add_node("preprocessor", preprocessor_agent)
    graph.add_node("transcription", transcription_agent)
    graph.add_node("diarization", diarization_agent)
    graph.add_node("entity_extractor", entity_extractor_agent)
    graph.add_node("summarizer", summarizer_agent)
    graph.add_node("evaluator", evaluation_agent)
    graph.add_node("vector_indexer", vector_indexer_agent)
    graph.add_node("graph_knowledge_builder", graph_knowledge_builder_agent)
    graph.add_node("semantic_cache", save_semantic_cache)
    graph.add_node("output_assembler", output_assembler)

    # ── Define Edges ─────────────────────────────────────────────────────────
    graph.add_edge(START, "audio_profiler")

    graph.add_conditional_edges(
        "audio_profiler",
        route_after_profiler,
        {"preprocess": "preprocessor", "end": "output_assembler"},
    )

    graph.add_edge("preprocessor", "transcription")

    graph.add_conditional_edges(
        "transcription",
        route_after_transcription,
        {"diarize": "diarization", "end": "output_assembler"},
    )

    graph.add_edge("diarization", "entity_extractor")
    graph.add_edge("entity_extractor", "summarizer")
    graph.add_edge("summarizer", "evaluator")

    # ── PARALLEL: vector_indexer ║ graph_knowledge_builder ───────────────────
    # Both nodes are independent (no shared state mutations), run concurrently
    graph.add_edge("evaluator", "vector_indexer")
    graph.add_edge("evaluator", "graph_knowledge_builder")
    graph.add_edge("vector_indexer", "semantic_cache")
    graph.add_edge("graph_knowledge_builder", "semantic_cache")

    graph.add_edge("semantic_cache", "output_assembler")
    graph.add_edge("output_assembler", END)

    return graph.compile(checkpointer=checkpointer)
