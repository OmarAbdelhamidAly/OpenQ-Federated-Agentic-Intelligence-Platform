"""Problem Diagnosis Service.

Uses LLM to analyze a user's business problem description against a data schema
and suggests 1-5 diagnostic analytical scenarios.
"""

import json
from typing import List, Dict, Any, Tuple
import structlog
from app.infrastructure.llm import get_llm

logger = structlog.get_logger(__name__)

DIAGNOSIS_PROMPT = """You are a world-class Business Intelligence consultant.
A user has described a problem they are facing in their business. 
Your goal is to analyze their problem against the provided data schema and suggest between 1 and 5 analytical scenarios (visualizations/reports) that will help them diagnose or solve the root cause.

Rules:
1. Be professional and empathetic.
2. If the user is non-technical, translate their problem into specific data questions.
3. Each suggestion must be directly answerable from the schema.
4. Provide a reasoning for why this analysis helps.
5. Rank suggestions by Priority (1 = Highest, 5 = Lowest).

Schema Summary:
{schema}

User's Problem Description:
{problem}

Return your response as a JSON object with this exact structure:
{{
    "problem_summary": "A concise, professional re-statement of the user's issue",
    "suggestions": [
        {{
            "text": "Specific natural language question for analysis",
            "reasoning": "Why this helps the user",
            "impact": "What they will learn or be able to do",
            "priority": 1
        }}
    ]
}}
"""

async def diagnose_problem(problem_description: str, schema_json: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a problem description and return suggested scenarios."""
    llm = get_llm(temperature=0.4) # Slightly higher temp for creative brainstorming
    
    # Prune schema to save tokens if it's too large, but keep the structure
    compact_schema = {
        "tables": [
            {
                "table": t["table"],
                "columns": [{"name": c["name"], "dtype": c["dtype"]} for c in t.get("columns", [])]
            }
            for t in schema_json.get("tables", [])
        ]
    }
    
    prompt = DIAGNOSIS_PROMPT.format(
        schema=json.dumps(compact_schema, separators=(',', ':')),
        problem=problem_description
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
        return parsed
    except Exception as e:
        logger.error("diagnosis_failed", error=str(e))
        return {
            "problem_summary": "We encountered an issue analyzing your problem details.",
            "suggestions": [
                {
                    "text": "Can you provide a general overview of the data trends?",
                    "reasoning": "Fallback suggestion due to analysis error.",
                    "impact": "General visibility",
                    "priority": 3
                }
            ]
        }
