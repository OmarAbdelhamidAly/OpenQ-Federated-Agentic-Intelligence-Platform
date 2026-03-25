"""Guardrail Agent — validates analysis plans against system policies."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings

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

Respond in JSON format:
{{
  "status": "compliant" | "violated",
  "reason": null | "..."
}}

Wait, there's more. If the plan is 'violated', the system will try to re-generate the plan. Be helpful but strict.
"""


async def guardrail_agent(state: AnalysisState) -> Dict[str, Any]:
    """Validate the generated analysis plan or SQL query."""
    policies = state.get("system_policies", [])
    if not policies:
        return {"policy_violation": None}

    llm = get_llm(temperature=0)

    # Prepare inputs
    analysis_results = state.get("analysis_results", {})
    plan = json.dumps(analysis_results.get("plan", {}), indent=2)
    policies_str = json.dumps(policies, indent=2)
    columns_str = json.dumps(state.get("relevant_columns", []), indent=2)

    prompt = GUARDRAIL_PROMPT.format(
        policies=policies_str,
        plan=plan,
        columns=columns_str
    )

    response = await llm.ainvoke(prompt)
    content = response.content

    try:
        # Strip markdown code fences if present
        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            parsed = json.loads(content)
        else:
            parsed = {"status": "compliant"}
    except json.JSONDecodeError:
        parsed = {"status": "compliant"}

    if parsed.get("status") == "violated":
        return {"policy_violation": parsed.get("reason", "Policy violation detected.")}

    return {"policy_violation": None}
