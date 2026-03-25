"""JSON Recommendation Agent."""

import logging
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

logger = logging.getLogger(__name__)

REC_PROMPT = """You are a Strategic Advisor.
Based on the JSON analysis insights below, provide 2-3 specific recommendations and 2 follow-up questions the user could ask.

INSIGHTS:
{insights}

Return JSON strictly in this format:
{{
  "recommendations": [
    {{"title": "Actionable Step 1", "description": "Why and how..."}},
    {{"title": "Actionable Step 2", "description": "Why and how..."}}
  ],
  "follow_up_suggestions": [
    "Could we group this by region?",
    "What is the trend over time?"
  ]
}}"""

async def recommendation_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate strategic recommendations based on the JSON insights."""
    insights = state.get("insight_report")
    if not insights:
        return {}

    llm = get_llm(temperature=0.4)
    prompt = REC_PROMPT.format(insights=insights[:2000])

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        import json
        config = json.loads(content)
        return config
    except Exception as e:
        logger.error("json_rec_failed", error=str(e))
        return {
            "recommendations": [{"title": "Explore further", "description": "Review the data manually."}],
            "follow_up_suggestions": ["Can you filter the data differently?"]
        }
