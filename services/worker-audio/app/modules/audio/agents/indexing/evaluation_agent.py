"""Evaluation Agent — Node 7 (Non-blocking).

Reuses the same RAGEvaluator as worker-pdf/worker-sql.
Treats speaker_turns as "chunks" and insight_report as "response".
"""
from __future__ import annotations
import structlog
from typing import Any, Dict, List
from app.domain.analysis.entities import AudioAnalysisState
from app.modules.audio.utils.rag_evaluator import get_evaluator

logger = structlog.get_logger(__name__)


def _turns_to_chunks(speaker_turns: list) -> List[Dict[str, Any]]:
    """Convert speaker turns into chunk format expected by RAGEvaluator."""
    return [
        {
            "chunk_id": f"turn_{i}",
            "text": turn.get("text", ""),
            "page_num": 0,
            "element_type": f"SpeakerTurn_{turn.get('speaker_id', 'SPEAKER_01')}",
        }
        for i, turn in enumerate(speaker_turns)
        if turn.get("text", "").strip()
    ]


async def evaluation_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Compute RAG quality metrics for the audio pipeline."""
    question = state.get("question", "")
    speaker_turns = state.get("speaker_turns", [])
    insight_report = state.get("insight_report", "")

    if not speaker_turns or not insight_report:
        logger.info("audio_evaluation_skipped", reason="no turns or report")
        return {"evaluation_metrics": None}

    logger.info("audio_evaluation_started", turns=len(speaker_turns))

    try:
        chunks = _turns_to_chunks(speaker_turns)
        evaluator = get_evaluator()
        eval_result = await evaluator.evaluate_retrieval(
            query=question,
            chunks=chunks,
            response=insight_report,
        )
        metrics = eval_result.to_dict()
        logger.info(
            "audio_evaluation_complete",
            avg_relevance=round(eval_result.avg_relevance, 3),
            attribution_rate=round(eval_result.attribution_rate, 3),
        )
        return {"evaluation_metrics": metrics}
    except Exception as e:
        logger.error("audio_evaluation_failed", error=str(e))
        return {"evaluation_metrics": {"error": str(e)}}
