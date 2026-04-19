from app.infrastructure.config import settings
"""Fast Text Synthesis Agent — Master Orchestrator Node.

This node performs final answer synthesis for text-heavy queries using 
previously retrieved chunks from the vector database.
"""
from __future__ import annotations

import structlog
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

logger = structlog.get_logger(__name__)


async def fast_text_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """Synthesis node for text-based RAG results."""
    question = state.get("question")
    search_results = state.get("search_results")
    history = state.get("history", [])

    if not search_results:
        return {"insight_report": "I could not find any relevant text in the document to answer your question."}

    logger.info("fast_text_synthesis_started", num_chunks=len(search_results))

    # Construct context from search results
    context_text = ""
    for i, res in enumerate(search_results):
        page = res.payload.get("page_num", "unknown")
        # Extract full parent page text if available, fallback to the chunk's text or standard description
        text = res.payload.get("parent_text") or res.payload.get("text") or res.payload.get("description", "")
        context_text += f"--- [CHUNK {i+1} | PAGE {page}] ---\n{text}\n\n"

    # Synthesis via fast LLM (standard Chat model, no vision needed here)
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_PDF)
    
    history_context = ""
    if history:
        history_context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-3:]])

    prompt = f"""You are a professional Document Analyst. Use the following context to answer the user's question accurately.
    
    RULES:
    1. If the answer is not in the context, say you don't know.
    2. Maintain a professional tone.
    3. Use the same language as the user.
    
    DOCUMENT CONTEXT:
    {context_text}
    
    CHAT HISTORY:
    {history_context}
    
    USER QUESTION: {question}
    
    YOUR ANALYSIS:"""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        return {
            "insight_report": res.content,
            "executive_summary": f"Text analysis complete using {len(search_results)} relevant chunks."
        }
    except Exception as e:
        logger.error("fast_text_synthesis_failed", error=str(e))
        return {"error": f"Synthesis failed: {str(e)}"}
