"""SQL Pipeline — Reflection Agent.

Analyzes execution errors or empty results and attempts to repair the SQL query.
Uses schema context (tables, columns, samples) to perform semantic mapping repairs.
CRITICAL FIX: Now includes the original question + safety gate against query simplification.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm

REFLECTION_PROMPT = """You are a senior SQL expert and self-correction agent.
The previous SQL query FAILED or yielded zero rows. Your task is to analyze ONLY the specific error and provide a minimally-repaired SQL query that still answers the ORIGINAL question.

⚠️ CRITICAL RULES — NEVER VIOLATE THESE:
1. PRESERVE THE ORIGINAL INTENT. The repaired query MUST still answer the original question below.
2. NEVER simplify or reduce the complexity. If it required 5-table JOINs before, keep 5-table JOINs.
3. NEVER replace a complex analytical query with a simple fallback like "SELECT * FROM SomeTable LIMIT n".
4. If the error is "Column not found", find the correct column name in the schema — do NOT remove that column or the JOIN.
5. If query returned 0 rows, check: incorrect JOIN conditions, wrong column case, over-restrictive WHERE filters.
6. Fix ONLY the specific issue — change the minimum possible while keeping all JOINs and aggregations intact.
7. Respond ONLY with a valid JSON object containing the repaired query.

ORIGINAL USER QUESTION (the repaired query MUST fully answer this):
{question}

AVAILABLE SCHEMA (use ONLY columns that exist here):
{schema_context}

PREVIOUS QUERY THAT FAILED:
{previous_query}

SPECIFIC ERROR / ISSUE TO FIX:
{error}

REPAIRED QUERY (JSON — must still fully answer the original question):
{{
  "query": "SELECT ... (full corrected query preserving all original JOINs and aggregations)",
  "explanation": "Exactly what was wrong and what was changed"
}}"""


async def reflection_agent(state: AnalysisState) -> Dict[str, Any]:
    """Analyze the error and repair SQL — preserving original intent."""
    error = state.get("error") or state.get("reflection_context")
    if not error:
        return {}

    retry_count = state.get("retry_count", 0)
    if retry_count >= 3:
        return {"error": f"Max retries reached. Last error: {error}"}

    # Build schema context for the LLM
    schema = state.get("schema_summary", {})
    tables = schema.get("tables", [])
    schema_context = "AVAILABLE SCHEMA:\n"
    for table in tables:
        schema_context += f"Table: {table['table']}\n"
        for col in table.get("columns", []):
            schema_context += f"  - {col['name']} ({col.get('dtype', 'unknown')}) | samples: {col.get('low_cardinality_values', [])}\n"

    previous_query = state.get("generated_sql") or "No query generated yet."
    original_question = state.get("question", "No question available.")

    llm = get_llm(temperature=0)
    prompt = REFLECTION_PROMPT.format(
        question=original_question,
        schema_context=schema_context,
        previous_query=previous_query,
        error=error
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # Clean markdown if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        repaired_data = json.loads(content)
        repaired_query = repaired_data.get("query", "").strip()

        # ── Safety Gate ────────────────────────────────────────────────────────
        # Reject if reflection produced a trivially simplified query.
        # A legit repair of a complex analytical query should always have JOINs.
        if repaired_query and previous_query and previous_query != "No query generated yet.":
            repaired_upper = repaired_query.upper()
            original_upper = previous_query.upper()
            original_join_count = original_upper.count("JOIN")

            is_trivial_fallback = (
                repaired_query.upper().startswith("SELECT * FROM")
                or (
                    "JOIN" not in repaired_upper
                    and original_join_count >= 2
                )
                or (
                    "LIMIT 10" in repaired_upper
                    and "JOIN" not in repaired_upper
                )
            )

            if is_trivial_fallback:
                # Reject simplified query — restore original and surface the error
                return {
                    "generated_sql": previous_query,
                    "error": (
                        f"[Reflection Safety Gate] Rejected simplified fallback query. "
                        f"Original complex query preserved. Root error was: {error}"
                    ),
                    "reflection_context": None,
                    "retry_count": retry_count + 1,
                }
        # ───────────────────────────────────────────────────────────────────────

        return {
            "generated_sql": repaired_query,
            "error": None,
            "reflection_context": None,  # Clear context for next run
            "retry_count": retry_count + 1,
        }
    except Exception as e:
        return {"error": f"Reflection failed to repair query: {str(e)}"}
