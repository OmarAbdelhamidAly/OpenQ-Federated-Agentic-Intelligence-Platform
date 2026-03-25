"""JSON Insight Agent."""

import json
import logging
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

logger = logging.getLogger(__name__)

INSIGHT_PROMPT = """You are a Senior Data Analyst.
Analyze the results from a MongoDB aggregation to answer the user's question.

USER QUESTION: {question}
MONGODB PIPELINE THAT WAS EXECUTED:
{query}

RESULTS PREVIEW (max 100):
{data}

Provide a concise, executive-level summary answering the question based on the data provided. Use markdown formatting."""

async def insight_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate actionable insights from the MongoDB results."""
    analysis = state.get("analysis_results") or {}
    if not analysis or not analysis.get("data"):
        return {"insight_report": "No data returned from MongoDB."}

    llm = get_llm(temperature=0.3)
    data_sample = analysis["data"][:100]
    
    prompt = INSIGHT_PROMPT.format(
        question=state.get("question", "Analyze the data"),
        query=json.dumps(analysis.get("query", []), indent=2),
        data=json.dumps(data_sample, indent=2, default=str)
    )

    try:
        response = await llm.ainvoke(prompt)
        return {
            "insight_report": response.content,
            "executive_summary": "Extracted insights from MongoDB aggregation."
        }
    except Exception as e:
        logger.error("json_insight_failed", error=str(e))
        return {"insight_report": "Failed to generate insights."}
