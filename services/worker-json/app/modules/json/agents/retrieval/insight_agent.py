"""JSON Pipeline — Insight Agent.

Generates premium strategic analysis and executive summary from JSON/MongoDB analysis results.
Upgraded to Premium Executive Narrative style (matching SQL/CSV pipelines).
"""

from __future__ import annotations

import json
import re
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

INSIGHT_PROMPT = """You are a Lead Business Intelligence Strategy Consultant.
Your goal is to transform raw JSON/MongoDB results into a premium, executive-grade analytical narrative that drives decision-making.

### REPORTING STYLE GUIDE
1. **Tone**: Professional, authoritative, and strategic.
2. **Structure**: 
   - Use Markdown headings (`###`).
   - Use bold text for key figures/entities.
   - Use bullet points for readability.
3. **Sections**:
   - **### 📈 Strategic Analysis**: Deep dive into the data, identifying trends, outliers, or significant rankings.
   - **### 🎯 Business Implications**: Explain what these numbers mean for the business (ROI, Risks, Opportunities).
   - **### 🛠️ Visualization Intelligence**: Explain why the chosen chart was selected for this data (using the context provided below).

### FORMATTING RULES (STRICT)
- Respond with ONLY a valid JSON object.
- The `insight_report` and `executive_summary` fields MUST contain RAW text with Markdown formatting.
- DO NOT use JSON-escaped quotes like \" inside the text; use single quotes ' or avoid them.

### INPUT DATA
- **User Question**: {question}
- **Analytical Intent**: {intent}
- **Visualization Logic**: {viz_rationale}
- **MongoDB Pipeline**: {query}
- **Data Sample**: {data}

JSON Structure:
{{
  "insight_report": "Full markdown report here...",
  "executive_summary": "Punchy one-sentence summary for the CEO dashboard."
}}"""


async def insight_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate written analysis and executive summary from JSON results."""
    analysis = state.get("analysis_results") or {}
    if not analysis or not analysis.get("data"):
        return {
            "insight_report": "No data returned for analysis.",
            "executive_summary": "Analysis yielded no results.",
        }

    llm = get_llm(temperature=0.3)

    def _sanitize_question(q: str) -> str:
        try:
            parsed = json.loads(q)
            if isinstance(parsed, dict) and "text" in parsed:
                return parsed["text"]
        except:
            pass
        return q

    prompt = INSIGHT_PROMPT.format(
        question=_sanitize_question(state.get("question") or ""),
        intent=state.get("intent") or "comparison",
        viz_rationale=state.get("viz_rationale") or "Standard automated selection.",
        query=json.dumps(analysis.get("query", []), indent=2),
        data=json.dumps(analysis.get("data", [])[:20], indent=2, default=str)
    )

    try:
        # Request JSON output
        response = await llm.ainvoke(prompt)
        content = response.content
        parsed = _parse_json(content)

        return {
            "insight_report": parsed.get("insight_report", "Analysis completed."),
            "executive_summary": parsed.get("executive_summary", "See detailed report."),
        }
    except Exception as e:
        logger.error("json_insight_generation_failed", error=str(e))
        return {
            "insight_report": f"Analysis complete. (Insight generation error: {str(e)[:50]})",
            "executive_summary": "Results are available in chart form.",
        }


def _parse_json(content: str) -> Dict[str, Any]:
    """Extract JSON object from LLM response with fallback extraction."""
    if not isinstance(content, str) or not content.strip():
        return {}
    
    content = content.strip()
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            raw_json = json_match.group().strip()
            parsed = json.loads(raw_json)
            for key in ["insight_report", "executive_summary"]:
                if key in parsed and isinstance(parsed[key], str):
                    val = parsed[key].strip()
                    val = re.sub(r'^```[a-z]*\n|```$', '', val, flags=re.MULTILINE)
                    parsed[key] = val
            return parsed
        except json.JSONDecodeError:
            pass
    return {}
