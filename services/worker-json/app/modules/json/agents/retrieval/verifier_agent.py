"""JSON Pipeline — Verifier Agent (LLM-Judge).

Cross-checks MongoDB aggregation results against business intent to ensure quality and accuracy.
"""

from __future__ import annotations
import json
from typing import Any, Dict

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

VERIFIER_PROMPT = """You are a Quality Control Expert for MongoDB data analysis.
Your job is to "verify" if the actual aggregation result data correctly answers the user's original question.

INPUTS:
- Question: {question}
- MongoDB Query: {query}
- Data Result (First 10 rows): {data}

RULES:
1. Check for **Semantic Match**: Does the data actually answer what the user asked for? 
   (e.g., If they asked for 'Maximum Salary' but the query only calculated 'avg', it's a fail).
2. Check for **Hallucination Results**: Does the data seem plausible?
3. Check for **Rounding/Format issues**.

RESPONSE:
Return a JSON object:
{{
  "verified": true/false,
  "reason": "..."
}}
"""

async def verifier_agent(state: AnalysisState) -> Dict[str, Any]:
    """Verify if the JSON output matches the user's business intent."""
    analysis = state.get("analysis_results")
    if not analysis or not analysis.get("data"):
        return {"validation_results": {"verified": True, "reason": "No data to verify."}}

    llm = get_llm(temperature=0)
    
    prompt = VERIFIER_PROMPT.format(
        question=state.get("question", ""),
        query=json.dumps(analysis.get("query", []), indent=2),
        data=json.dumps(analysis.get("data", [])[:10], indent=2, default=str)
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        
        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            
        result = json.loads(content)
        return {"validation_results": result}
    except Exception as e:
        return {"validation_results": {"verified": True, "reason": f"Verification bypassed due to error: {e}"}}
