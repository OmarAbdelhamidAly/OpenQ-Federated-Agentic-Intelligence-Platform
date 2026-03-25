"""SQL Pipeline — Insight Agent.

Generates written analysis and executive summary from SQL analysis results.
Source-agnostic logic — identical to the CSV version, both kept
separate so each pipeline folder is self-contained.
"""

from __future__ import annotations

import json
import re
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings

INSIGHT_PROMPT = """You are a senior data analyst writing insights for business stakeholders.

Based on the analysis results and supplemental knowledge base context, write:

1. **insight_report**: A detailed analysis in plain English (3-5 paragraphs).
   - Always quantify findings: "23% drop" not just "dropped".
   - Reference specific data points.
   - **Hybrid Reasoning**: If Knowledge Base context is provided, cross-reference the numbers with the policies/guidelines found in the context.

2. **executive_summary**: Max 3 sentences. Plain English. No jargon.
   - Lead with the headline finding.
   - Include the key number.
   - State the implication.

Respond in STRICT JSON format. 
NO PREAMBLE. NO EXPLANATION. JUST THE JSON OBJECT.

{{
  "insight_report": "...",
  "executive_summary": "..."
}}

Question: {question}
Intent: {intent}
Knowledge Base Context: {kb_context}
Data: {data}

{complexity_instruction}"""


async def insight_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate written analysis and executive summary from SQL results."""
    analysis = state.get("analysis_results") or {}
    if not analysis:
        error_msg = state.get("error") or "No analysis data available."
        return {
            "insight_report": f"Analysis could not be completed. Details: {error_msg}",
            "executive_summary": "Analysis could not be completed.",
        }

    llm = get_llm(temperature=0.3)

    # Calculate complexity instructions (Idea: Dynamic tone)
    idx = state.get("complexity_index", 1)
    tot = state.get("total_pills", 1)
    
    complexity_instruction = ""
    if tot > 1:
        if idx == 1:
            complexity_instruction = "TONE: Tactical & Foundational. Focus on the immediate facts. Keep the analysis grounded in the specific numbers provided."
        elif idx == tot:
            complexity_instruction = f"TONE: Strategic & Executive. This is the master insight (level {idx}). Provide a high-level summary that synthesizes the implications for the business. Focus on ROI, growth, or risk."
        else:
            complexity_instruction = f"TONE: Investigative & Advanced. Dig into the 'why'. Look for second-order effects or trends that are not immediately obvious at first glance."

    prompt = INSIGHT_PROMPT.format(
        question=state.get("question") or "",
        intent=state.get("intent") or "comparison",
        kb_context=analysis.get("kb_context") or "None provided.",
        data=json.dumps(analysis.get("data", [])[:20], indent=2, default=str),
        complexity_instruction=complexity_instruction
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        parsed = _parse_json(content)

        if not parsed:
            logger.warning("insight_parsing_empty", content=content)
            raise ValueError("Parsed insight JSON is empty")

        return {
            "insight_report": parsed.get("insight_report", "Analysis completed."),
            "executive_summary": parsed.get("executive_summary", "See detailed report."),
        }
    except Exception as e:
        logger.error("insight_generation_failed", error=str(e), content=content if 'content' in locals() else None)
        return {
            "insight_report": f"Analysis was performed but insight generation encountered an error: {str(e)[:100]}",
            "executive_summary": "Results are available in chart form.",
        }


def _parse_json(content: Any) -> Dict[str, Any]:
    """Ultra-resilient JSON parser for Llama-3/Groq responses."""
    if not isinstance(content, str) or not content.strip():
        return {}

    content = content.strip()
    
    # 1. Be aggressive: look for the first { and last } regardless of blocks
    start_idx = content.find('{')
    end_idx = content.rfind('}')
    
    if start_idx == -1 or end_idx == -1:
        return {}

    json_str = content[start_idx : end_idx + 1]

    # 2. Try standard load
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 3. Clean common issues and try again
    try:
        # Handle trailing commas before closing brackets
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
        # Handle control characters
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    return {}
    return {}
