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

INSIGHT_PROMPT = """You are a Lead Business Intelligence Strategy Consultant.
Your goal is to transform raw data into a premium, executive-grade analytical narrative that drives decision-making.

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

### CONTEXTUAL MEMORY
{running_summary}

### INPUT DATA
- **User Question**: {question}
- **Analytical Intent**: {intent}
- **Visualization Logic**: {viz_rationale}
- **Knowledge Base Insights**: {kb_context}
- **Data Sample**: {data}

Analytical level: {complexity_instruction}

JSON Structure:
{{
  "insight_report": "Full markdown report here...",
  "executive_summary": "Punchy one-sentence summary for the CEO dashboard."
}}"""


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

    # Calculate complexity instructions
    idx = state.get("complexity_index", 1)
    tot = state.get("total_pills", 1)
    
    complexity_instruction = "Standard analysis."
    if tot > 1:
        complexity_instruction = f"This is part {idx} of {tot}. Maintain consistency with previous steps."

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
        kb_context=analysis.get("kb_context") or "None provided.",
        data=json.dumps(analysis.get("data", [])[:20], indent=2, default=str),
        complexity_instruction=complexity_instruction,
        running_summary=state.get("running_summary", "No previous context.")
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        parsed = _parse_json(content)

        return {
            "insight_report": parsed.get("insight_report", "Analysis completed."),
            "executive_summary": parsed.get("executive_summary", "See detailed report."),
        }
    except Exception as e:
        logger.error("insight_generation_failed", error=str(e))
        return {
            "insight_report": f"Analysis complete. (Insight generation error: {str(e)[:50]})",
            "executive_summary": "Results are available in chart form.",
        }


def _parse_json(content: str) -> Dict[str, str]:
    """Extract JSON object from LLM response with fallback extraction."""
    import re
    
    if not content or not content.strip():
        return {}
    
    content = content.strip()
    
    # Try to find JSON block first
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            # Clean common LLM artifacts like escaped newlines or weird characters
            raw_json = json_match.group().strip()
            parsed = json.loads(raw_json)
            # Ensure the values themselves don't have residual JSON-like markers
            for key in ["insight_report", "executive_summary"]:
                if key in parsed and isinstance(parsed[key], str):
                    val = parsed[key].strip()
                    # Remove accidental markdown code block wrappers inside the string
                    val = re.sub(r'^```[a-z]*\n|```$', '', val, flags=re.MULTILINE)
                    parsed[key] = val
            return parsed
        except json.JSONDecodeError:
            pass
    
    # Fallback: Extract fields using regex
    result = {}
    
    # Look for insight_report field
    insight_match = re.search(r'["\']?insight_report["\']?\s*:\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if insight_match:
        result["insight_report"] = insight_match.group(1)
    
    # Look for executive_summary field  
    summary_match = re.search(r'["\']?executive_summary["\']?\s*:\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if summary_match:
        result["executive_summary"] = summary_match.group(1)
    
    return result if result else {}
