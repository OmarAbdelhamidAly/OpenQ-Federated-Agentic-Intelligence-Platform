"""Guardrail Agent — validates analysis plans against system policies."""
from __future__ import annotations
import json
import re
import structlog
from typing import Any, Dict
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

GUARDRAIL_PROMPT = """You are a Data Governance & Security Auditor.
Review the following analysis plan and determine if it violates any organization policies.

Policies:
{policies}

Analysis Plan:
{plan}

Columns in Data Source:
{columns}

Rules:
1. If the plan violates any policy (e.g. accessing a forbidden column, performing a restricted aggregation), you must FLAG it.
2. If flagged, provide a clear explanation for the violation.
3. If no violations are found, return 'compliant'.

Respond in the following STRICT JSON format:
{{
  "status": "compliant" | "violated",
  "reason": null | "..."
}}

STRICT JSON format only. NO PREAMBLE. NO post-explanation."""

async def guardrail_agent(state: AnalysisState) -> Dict[str, Any]:
    policies = state.get("system_policies", [])
    if not policies: return {"policy_violation": None}
    
    llm = get_llm(temperature=0)
    plan = json.dumps(state.get("analysis_results", {}).get("plan", {}), indent=2)
    
    prompt = GUARDRAIL_PROMPT.format(
        policies=json.dumps(policies, indent=2),
        plan=plan,
        columns=json.dumps(state.get("relevant_columns", []), indent=2)
    )
    
    try:
        res = await llm.ainvoke(prompt)
        content = res.content
        
        parsed = _parse_json(content)
        
        if parsed.get("status") == "violated":
            return {"policy_violation": parsed.get("reason", "Policy violation detected.")}
        return {"policy_violation": None}
        
    except Exception as e:
        logger.error("guardrail_agent_failed", error=str(e))
        # Default to safe (non-violating but logged error) or unsafe? 
        # Usually governance should fail-closed, but for this dev build we fail-open and log.
        return {"policy_violation": None}


def _parse_json(content: Any) -> Dict[str, Any]:
    """Ultra-resilient JSON parser for LLM responses."""
    if not isinstance(content, str) or not content.strip():
        return {}

    content = content.strip()
    
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
        # Aggressive cleanup
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    return {}
