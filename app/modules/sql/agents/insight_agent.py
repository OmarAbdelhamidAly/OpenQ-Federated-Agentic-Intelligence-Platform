"""SQL Pipeline — Insight Agent.

Generates written analysis and executive summary from SQL analysis results.
Source-agnostic logic — identical to the CSV version, both kept
separate so each pipeline folder is self-contained.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings

INSIGHT_PROMPT = """You are a senior data analyst writing insights for business stakeholders.

Based on the analysis results, write:

1. **insight_report**: A detailed analysis in plain English (3-5 paragraphs).
   - Always quantify findings: "23% drop" not just "dropped".
   - Reference specific data points.
   - Explain the "why" behind the numbers when possible.

2. **executive_summary**: Max 3 sentences. Plain English. No jargon.
   - Lead with the headline finding.
   - Include the key number.
   - State the implication.

Respond in JSON format:
{{
  "insight_report": "...",
  "executive_summary": "..."
}}

Question: {question}
Intent: {intent}
Data: {data}"""


async def insight_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate written analysis and executive summary from SQL results."""
    analysis = state.get("analysis_results")
    if not analysis:
        error_msg = state.get("error") or "No analysis data available."
        return {
            "insight_report": f"Analysis could not be completed. Details: {error_msg}",
            "executive_summary": "Analysis could not be completed.",
        }

    llm = get_llm(temperature=0.3)

    prompt = INSIGHT_PROMPT.format(
        question=state.get("question", ""),
        intent=state.get("intent", "comparison"),
        data=json.dumps(analysis.get("data", [])[:20], indent=2, default=str),
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
            "insight_report": parsed.get("insight_report", "Analysis completed."),
            "executive_summary": parsed.get("executive_summary", "See detailed report."),
        }
    except Exception:
        return {
            "insight_report": "Analysis was performed but insight generation encountered an error.",
            "executive_summary": "Results are available in chart form.",
        }
