"""Fast Text RAG Agent — LangGraph Node.

Replaces the ColPali VLM retrieval node when indexing_mode == 'fast_text'.
Uses HNSW dense search + MMR + reranking to build context, then calls
the main LLM (text-only, no vision needed).
"""
from __future__ import annotations

import structlog
from typing import Any, Dict
from langchain_core.messages import HumanMessage

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm
from app.modules.pdf.utils.fast_retrieval import fast_retrieve_context

logger = structlog.get_logger(__name__)


async def fast_text_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """Fast text-based RAG agent node (no VLM, no GPU).

    Retrieval chain:
        HNSW dense search → MMR diversification → Cross-Encoder reranking → LLM
    """
    source_id = state.get("source_id")
    question = state.get("question", "")

    if not source_id:
        return {"error": "No source_id provided for Fast Text RAG."}

    logger.info("fast_text_rag_started", source_id=source_id, question=question[:80])

    try:
        # ── 1. Retrieve context (HNSW → MMR → Reranking) ──────────────────
        context = await fast_retrieve_context(
            source_id=source_id,
            query=question,
            top_k_final=5,
            top_k_hnsw=20,
            top_k_mmr=10,
        )

        if not context:
            return {
                "insight_report": (
                    "⚠️ No relevant content found for your query in this document.\n\n"
                    "This may be because the document is image-only (no extractable text). "
                    "Try re-uploading with **Deep Vision mode** enabled."
                ),
                "executive_summary": "Fast Text RAG: no matching chunks found.",
            }

        # ── 2. Build LLM Prompt ────────────────────────────────────────────
        system_prompt = (
            "You are an expert document analyst. "
            "You will answer the user's question based ONLY on the provided document context. "
            "Structure your response with: a direct answer, key insights, and any caveats. "
            "If the context does not contain the answer, say so clearly."
        )

        history_arr = state.get("history", [])
        chat_history = "No previous conversational context."
        if history_arr:
            chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

        user_prompt = (
            f"DOCUMENT CONTEXT:\n"
            f"{'='*60}\n"
            f"{context}\n"
            f"{'='*60}\n\n"
            f"CONVERSATIONAL MEMORY:\n"
            f"{chat_history}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"Please provide a comprehensive, structured answer."
        )

        llm = get_llm(temperature=0)
        res = await llm.ainvoke([
            HumanMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        insight = res.content if hasattr(res, "content") else str(res)
        logger.info("fast_text_rag_done", source_id=source_id, chars=len(insight))

        return {
            "insight_report": insight,
            "executive_summary": f"Fast Text RAG: retrieved {context.count('[Chunk')} chunks from '{source_id[:8]}...'",
        }

    except Exception as e:
        logger.error("fast_text_rag_failed", source_id=source_id, error=str(e))
        return {"error": f"Fast Text RAG failed: {str(e)}"}
