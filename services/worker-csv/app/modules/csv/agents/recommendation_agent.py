"""CSV Pipeline — Recommendation Agent.

Generates actionable recommendations and follow-up questions from CSV analysis results.
Source-agnostic logic — identical to the SQL version, both kept
separate so each pipeline folder is self-contained.
"""

from __future__ import annotations

import json
import re
import structlog
from typing import Any, Dict, List

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings

# Prompt synchronized with services/api/app/schemas/analysis.py -> RecommendationItem
REC_PROMPT = """You are a senior business consultant. Based on the data analysis results, 
provide strategic recommendations and follow-up data questions.

Provide your response in the following STRICT JSON format:
{{
  "recommendations": [
    {{
      "action": "Short title or title of the action to take",
      "expected_impact": "Detailed description of the expected business impact",
      "confidence_score": 85,
      "main_risk": "Primary risk or dependency"
    }}
  ],
  "follow_up_suggestions": [
    "Question starting with 'Why did...'",
    "Question starting with 'What if...'"
  ]
}}

STRICT JSON format only. NO PREAMBLE. NO post-explanation.
The "confidence_score" MUST be an integer between 0 and 100.

Question: {question}
Insight Report: {insight}
Executive Summary: {summary}"""


async def recommendation_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate recommendations and follow-up questions from CSV analysis."""
    insight = state.get("insight_report", "")
    summary = state.get("executive_summary", "")
    if not insight and not summary:
        return {"recommendations": [], "follow_up_suggestions": []}

    llm = get_llm(temperature=0)

    prompt = REC_PROMPT.format(
        question=state.get("question", ""),
        insight=insight,
        summary=summary,
    )

    try:
        res = await llm.ainvoke(prompt)
        content = res.content
        
        parsed = _parse_json(content)
        
        if not parsed:
            logger.warning("csv_recommendation_parsing_failed", content=content)
            return {
                "recommendations": [
                    {
                        "action": "Further Analysis Recommended",
                        "expected_impact": "Examine the trends shown in the chart for deeper operational insights.",
                        "confidence_score": 70,
                        "main_risk": "Data granularity may limit specific conclusions."
                    }
                ],
                "follow_up_suggestions": [
                    "What are the primary drivers of the observed trends?",
                    "How do these results compare to previous periods?"
                ]
            }

        # Filter the recommendations to ensure they match the schema
        recommendations = []
        for rec in parsed.get("recommendations", []):
            if isinstance(rec, dict):
                recommendations.append({
                    "action": str(rec.get("action") or rec.get("title", "Recommended Action")),
                    "expected_impact": str(rec.get("expected_impact") or rec.get("description", "Positive business impact.")),
                    "confidence_score": int(rec.get("confidence_score") if isinstance(rec.get("confidence_score"), (int, float)) else 80),
                    "main_risk": str(rec.get("main_risk") or "None identified.")
                })

        return {
            "recommendations": recommendations,
            "follow_up_suggestions": parsed.get("follow_up_suggestions", []),
        }

    except Exception as e:
        logger.error("csv_recommendation_generation_failed", error=str(e))
        return {
            "recommendations": [
                {
                    "action": "Manual Insight Required",
                    "expected_impact": "Recommendations could not be auto-generated for this specific data slice.",
                    "confidence_score": 50,
                    "main_risk": "Technical error during generation."
                }
            ],
            "follow_up_suggestions": [
                "Review raw data for anomalies.",
                "Consult with domain experts on these findings."
            ],
        }


def _parse_json(content: Any) -> Dict[str, Any]:
    """Ultra-resilient JSON parser for LLM responses."""
    if not isinstance(content, str) or not content.strip():
        return {}

    content = content.strip()
    
    # Extract JSON content between the first { and last }
    start_idx = content.find('{')
    end_idx = content.rfind('}')
    
    if start_idx == -1 or end_idx == -1:
        return {}

    json_str = content[start_idx : end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    try:
        # Aggressive cleanup: remove trailing commas and control characters
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    return {}
