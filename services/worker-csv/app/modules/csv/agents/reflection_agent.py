"""CSV Pipeline — Reflection Agent.

Analyzes execution errors or empty results and attempts to repair the analysis plan.
Uses schema context (columns, dtypes, samples) to perform semantic mapping repairs.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

REFLECTION_PROMPT = """You are a senior data analyst and self-correction agent.
The previous analysis plan FAILED. Your task is to analyze the error and the dataset schema, then provide a REPAIRED PLAN.

STRICT RULES:
1. If the error is "Column not found", find the most semantically similar column in the schema.
   Example: If the plan used "income" but the schema has "salary_monthly", use "salary_monthly".
2. If the result was empty, check if filters were too restrictive.
3. If the plan was nonsensical, simplify it.
4. Respond ONLY with the repaired JSON plan.

{schema_context}

PREVIOUS PLAN:
{previous_plan}

ERROR/ISSUE:
{error}

REPAIRED PLAN (JSON):"""

async def reflection_agent(state: AnalysisState) -> Dict[str, Any]:
    """Analyze the error and the schema to repair the analysis plan."""
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
        # Extract JSON from response
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        repaired_plan = json.loads(content)
        
        # We return the repaired plan in a way that the analysis agent can pick it up.
        # But actually, in our LangGraph, we can just jump back to 'analysis' node
        # if we inject the repaired plan into the state.
        
        return {
            "repaired_plan": repaired_plan,
            "error": None, # Clear the error for the next run
            "retry_count": retry_count + 1
        }
    except Exception as e:
        return {"error": f"Reflection failed to parse repaired plan: {str(e)}"}
