"""
Code RAG Evaluation Agent — LangGraph Node

Computes Chunk Relevance, Attribution, and Utilization metrics for every retrieved
code snippet against the user's question and the generated technical answer.
"""
from __future__ import annotations

import structlog
from typing import Any, Dict

from app.domain.analysis.entities import CodeAnalysisState
from app.modules.code.utils.rag_evaluator import get_evaluator

logger = structlog.get_logger(__name__)


async def evaluation_agent(state: CodeAnalysisState) -> Dict[str, Any]:
    """
    Computes RAG quality metrics for the current Code retrieval cycle.
    """
    question = state.get("question", "")
    code_snippets = state.get("code_snippets", [])
    insight_report = state.get("insight_report", "")

    # ── Skip if no data to evaluate ───────────────────────────────────────────
    if not code_snippets or not insight_report:
        logger.info("evaluation_agent_skipped",
                    reason="no code snippets or report")
        return {"evaluation_metrics": None}

    logger.info("evaluation_agent_started",
                chunks=len(code_snippets),
                question=question[:60])

    try:
        # Convert code_snippets into chunks for the evaluator
        chunks = []
        for i, snippet in enumerate(code_snippets):
            name = snippet.get("name", f"snippet_{i}")
            code = snippet.get("code", "")
            
            # Combine name and code for evaluation context
            text = f"File/Function: {name}\n```{code}```"
            
            chunks.append({
                "chunk_id": name,
                "text": text,
                "element_type": "CodeSnippet"
            })

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
        )

        return {"evaluation_metrics": metrics_dict}

    except Exception as e:
        logger.error("evaluation_agent_failed", error=str(e))
        return {
            "evaluation_metrics": {
                "error": str(e),
                "diagnosis": "Evaluation failed — RAG metrics unavailable.",
            }
        }
