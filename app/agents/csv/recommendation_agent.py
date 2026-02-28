"""CSV Pipeline — Recommendation Agent.

Generates actionable recommendations and follow-up questions from CSV analysis results.
Source-agnostic logic — identical to the SQL version, both kept
separate so each pipeline folder is self-contained.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from langchain_groq import ChatGroq

from app.agents.state import AnalysisState
from app.core.config import settings

REC_PROMPT = """You are a strategic business advisor. Based on the analysis results and insights,
generate actionable recommendations.

Provide exactly:
1. **recommendations**: A list of 2-3 items, each containing:
   - action: What to do (specific, actionable)
   - expected_impact: What will happen if they do it (quantify if possible)
   - confidence_score: 0-100 (how confident you are)
   - main_risk: What could go wrong

2. **follow_up_suggestions**: A list of 2-3 related questions the user can ask next
   to dig deeper into this analysis.

Respond in JSON format:
{{
  "recommendations": [
    {{
      "action": "...",
      "expected_impact": "...",
      "confidence_score": 80,
      "main_risk": "..."
    }}
  ],
  "follow_up_suggestions": [
    "What is the trend over the last 6 months?",
    "Which segment shows the highest growth?"
  ]
}}

Question: {question}
Insight Report: {insight}
Executive Summary: {summary}"""


async def recommendation_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate recommendations and follow-up questions from CSV analysis."""
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=settings.GROCK_API_KEY,
        temperature=0.3,
    )

    prompt = REC_PROMPT.format(
        question=state.get("question", ""),
        insight=state.get("insight_report", ""),
        summary=state.get("executive_summary", ""),
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            parsed = json.loads(content)
        else:
            parsed = {}

        return {
            "recommendations": parsed.get("recommendations", []),
            "follow_up_suggestions": parsed.get("follow_up_suggestions", []),
        }
    except Exception:
        return {
            "recommendations": [],
            "follow_up_suggestions": [
                "Can you break this down by time period?",
                "Which category contributes the most?",
            ],
        }
