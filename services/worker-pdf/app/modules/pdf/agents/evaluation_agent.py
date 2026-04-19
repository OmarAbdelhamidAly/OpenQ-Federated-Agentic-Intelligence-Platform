"""
RAG Evaluation Agent — LangGraph Node

Positioned after `analyst_agent` in the pipeline. Computes Chunk Relevance,
Attribution, and Utilization metrics for every retrieved chunk, then injects
the results into the pipeline state for storage and surfacing via the API.

This node is NON-BLOCKING: if evaluation fails (e.g., models unavailable),
it logs a warning and passes through without breaking the pipeline.
"""
from __future__ import annotations

import structlog
from typing import Any, Dict, List

from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.utils.rag_evaluator import get_evaluator

logger = structlog.get_logger(__name__)


async def evaluation_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Computes RAG quality metrics for the current retrieval cycle.

    Reads from state:
      - question        — User query
      - search_results  — Raw Qdrant ScoredPoints (with payload)
      - insight_report  — LLM-generated final response

    Writes to state:
      - evaluation_metrics — Full RetrievalEvaluation dict (stored in DB)
    """
    question = state.get("question", "")
    search_results = state.get("search_results", [])
    insight_report = state.get("insight_report", "")

    # ── Skip if no data to evaluate ───────────────────────────────────────────
    if not search_results or not insight_report:
        logger.info("evaluation_agent_skipped",
                    reason="no search results or report")
        return {"evaluation_metrics": None}

    logger.info("evaluation_agent_started",
                chunks=len(search_results),
                question=question[:60])

    try:
        # ── Convert Qdrant ScoredPoints → plain dicts ──────────────────────────
        chunks = _qdrant_hits_to_chunks(search_results)

        # ── Run evaluation ─────────────────────────────────────────────────────
        evaluator = get_evaluator()
        eval_result = await evaluator.evaluate_retrieval(
            query=question,
            chunks=chunks,
            response=insight_report,
        )

        metrics_dict = eval_result.to_dict()

        logger.info(
            "evaluation_agent_complete",
            attributed=eval_result.attributed_chunks,
            total=eval_result.total_chunks,
            avg_relevance=round(eval_result.avg_relevance, 3),
            avg_utilization=round(eval_result.avg_utilization, 3),
            attribution_rate=round(eval_result.attribution_rate, 3),
            diagnosis=eval_result.diagnosis[:80],
        )

        return {"evaluation_metrics": metrics_dict}

    except Exception as e:
        # Non-blocking: log and continue without metrics
        logger.error("evaluation_agent_failed", error=str(e))
        return {
            "evaluation_metrics": {
                "error": str(e),
                "diagnosis": "Evaluation failed — RAG metrics unavailable.",
            }
        }


def _qdrant_hits_to_chunks(search_results: Any) -> List[Dict[str, Any]]:
    """
    Converts Qdrant ScoredPoint objects to plain chunk dicts for the evaluator.

    Handles both:
    - Qdrant ScoredPoint objects (production)
    - Plain dicts (testing / mocked results)
    """
    chunks = []
    for hit in search_results:
        # Handle Qdrant ScoredPoint objects
        if hasattr(hit, "payload"):
            payload = hit.payload or {}
            chunk_id = str(hit.id) if hasattr(hit, "id") else f"chunk_{len(chunks)}"
        elif isinstance(hit, dict):
            payload = hit
            chunk_id = hit.get("id", f"chunk_{len(chunks)}")
        else:
            continue

        # Extract text — prefer child chunk text for precision
        text = (
            payload.get("text")
            or payload.get("description")
            or payload.get("parent_text")
            or ""
        )

        if not text:
            continue

        chunks.append({
            "chunk_id": chunk_id,
            "text": text,
            "page_num": payload.get("page_num", 0),
            "element_type": payload.get("element_type", "Unknown"),
        })

    return chunks
