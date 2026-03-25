"""JSON Pipeline — Reflection Agent."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

REFLECTION_PROMPT = """You are a senior data engineer and self-correction agent.
The previous MongoDB aggregation plan FAILED. Your task is to analyze the error and the dataset schema, then provide a REPAIRED PLAN.

STRICT RULES:
1. Fix syntax errors in the pipeline.
2. If a field doesn't exist, map it to the semantically closest field in the schema.
3. Respond ONLY with the repaired JSON plan.

AVAILABLE SCHEMA:
{schema_context}

PREVIOUS PLAN:
{previous_plan}

ERROR/ISSUE:
{error}

OUTPUT FORMAT (JSON ONLY):
{{
  "operation": "aggregate",
  "pipeline": [...]
}}"""

async def reflection_agent(state: AnalysisState) -> Dict[str, Any]:
    """Analyze the error and the schema to repair the Mongo aggregation plan."""
    error = state.get("error")
    if not error:
        return {}

    retry_count = state.get("retry_count", 0)
    if retry_count >= 3:
        return {"error": f"Max retries reached. Last error: {error}"}

    # Build schema context for the LLM
    schema = state.get("schema_summary", {})
    columns = schema.get("columns", [])
    schema_context = "AVAILABLE SCHEMA:\n"
    for col in columns:
        schema_context += f"- {col['name']} ({col['dtype']}) | samples: {col.get('sample_values', [])}\n"

    previous_plan = json.dumps(state.get("analysis_results", {}).get("plan", {}), indent=2)
    
    llm = get_llm(temperature=0)
    prompt = REFLECTION_PROMPT.format(
        schema_context=schema_context,
        previous_plan=previous_plan,
        error=error
    )
    
    response = await llm.ainvoke(prompt)
    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        repaired_plan = json.loads(content)
        
        return {
            "repaired_plan": repaired_plan,
            "error": None,
            "retry_count": retry_count + 1
        }
    except Exception as e:
        return {"error": f"Reflection failed to parse repaired plan: {str(e)}"}
