"""CSV Pipeline — Analysis Agent.

Uses an LLM to generate a pandas-based analysis plan, then dispatches
to the correct CSV tool (compute_trend, compute_correlation, compute_ranking,
or run_pandas_query).

Includes retry logic: up to 3 attempts on failure.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from langchain_groq import ChatGroq

from app.agents.state import AnalysisState
from app.core.config import settings
from app.tools.load_data_source import resolve_data_path

# ── Prompt ────────────────────────────────────────────────────────────────────

CSV_ANALYSIS_PROMPT = """You are a data analyst. Given the user question, schema, and intent,
write a precise analysis plan as JSON.

Intent values and what tool they map to:
- trend       → use operation "trend" with date_column and value_column
- correlation → use operation "correlation" with optional columns list
- ranking     → use operation "ranking" with rank_column, label_column, top_n
- comparison  → use operation "groupby" with group_by, agg_column, agg_function
- anomaly     → use operation "trend" (anomaly detection is built-in to trend tool)
- (default)   → use operation "sort", "filter", "aggregate", or "groupby"

Respond ONLY with valid JSON. No explanations. No markdown.

Fields:
{{
  "operation": "groupby|filter|aggregate|sort|pivot|trend|correlation|ranking",
  "group_by": ["col1"],
  "agg_column": "col",
  "agg_function": "sum|mean|count|max|min",
  "sort_by": "col",
  "sort_order": "asc|desc",
  "top_n": 10,
  "filter_conditions": [{{"column": "col", "operator": "==", "value": "val"}}],
  "date_column": "col",
  "value_column": "col",
  "rank_column": "col",
  "label_column": "col"
}}

Schema: {schema}
Question: {question}
Intent: {intent}
Relevant columns: {columns}
{error_hint}"""


# ── Main Agent ────────────────────────────────────────────────────────────────

async def analysis_agent(state: AnalysisState) -> Dict[str, Any]:
    """Run the CSV analysis using LLM-generated plan dispatched to safe pandas tools.

    Includes retry logic: up to 3 attempts on failure.
    The LLM only decides WHAT to compute — actual execution goes through
    validated, injection-safe tool functions.
    """
    retry_count = state.get("retry_count", 0)
    previous_error = state.get("error")

    error_hint = ""
    if previous_error and retry_count > 0:
        error_hint = f"\n\nPrevious attempt failed with: {previous_error}\nPlease adjust your approach."

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=settings.GROCK_API_KEY,
        temperature=0,
    )

    schema_str = json.dumps(state.get("schema_summary", {}), indent=2)
    intent = state.get("intent", "comparison")
    columns = json.dumps(state.get("relevant_columns", []))

    try:
        return await _run_csv_analysis(
            llm, state, schema_str, intent, columns, error_hint, retry_count
        )
    except Exception as exc:
        return {
            "error": str(exc),
            "retry_count": retry_count + 1,
        }


# ── CSV Analysis ──────────────────────────────────────────────────────────────

async def _run_csv_analysis(
    llm, state, schema_str, intent, columns, error_hint, retry_count
) -> Dict[str, Any]:
    """Generate an analysis plan and dispatch it to the correct CSV tool."""
    prompt = CSV_ANALYSIS_PROMPT.format(
        schema=schema_str,
        question=state["question"],
        intent=intent,
        columns=columns,
        error_hint=error_hint,
    )

    response = await llm.ainvoke(prompt)
    plan = _parse_json(response.content)

    data_path = resolve_data_path(state)
    if not data_path:
        return {
            "error": "No CSV file path available in state.",
            "retry_count": retry_count + 1,
        }

    operation = plan.get("operation", "groupby")
    analysis_results = _dispatch_csv_tool(data_path, operation, plan)

    return {
        "analysis_results": {
            "plan": plan,
            "source_type": "csv",
            **analysis_results,
        },
        "error": None,
        "retry_count": retry_count,
    }


def _dispatch_csv_tool(data_path: str, operation: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Route to the correct CSV tool based on operation from the LLM plan."""

    if operation == "trend":
        from app.tools.csv.compute_trend import compute_trend
        date_col = plan.get("date_column", "")
        value_col = plan.get("value_column") or plan.get("agg_column", "")
        if not date_col or not value_col:
            raise ValueError("'trend' operation requires date_column and value_column in the plan.")
        return compute_trend.invoke({
            "file_path": data_path,
            "date_column": date_col,
            "value_column": value_col,
            "group_by": plan.get("group_by") if isinstance(plan.get("group_by"), str) else None,
        })

    elif operation == "correlation":
        from app.tools.csv.compute_correlation import compute_correlation
        cols = plan.get("columns") or plan.get("group_by") or None
        if isinstance(cols, str):
            cols = [cols]
        return compute_correlation.invoke({
            "file_path": data_path,
            "columns": cols,
            "method": "pearson",
        })

    elif operation == "ranking":
        from app.tools.csv.compute_ranking import compute_ranking
        rank_col = plan.get("rank_column") or plan.get("agg_column", "")
        label_col = plan.get("label_column") or (
            plan.get("group_by")[0] if isinstance(plan.get("group_by"), list) and plan.get("group_by")
            else plan.get("group_by", "")
        )
        if not rank_col or not label_col:
            raise ValueError("'ranking' operation requires rank_column and label_column in the plan.")
        return compute_ranking.invoke({
            "file_path": data_path,
            "rank_column": rank_col,
            "label_column": label_col,
            "top_n": plan.get("top_n", 10),
            "sort_order": plan.get("sort_order", "desc"),
            "date_column": plan.get("date_column"),
        })

    else:
        # Default: run_pandas_query handles groupby, filter, aggregate, sort, pivot
        from app.tools.csv.run_pandas_query import run_pandas_query

        # Normalise group_by to list
        group_by = plan.get("group_by")
        if isinstance(group_by, str):
            group_by = [group_by]

        safe_op = operation if operation in ("groupby", "filter", "aggregate", "sort", "pivot") else "sort"

        return run_pandas_query.invoke({
            "file_path": data_path,
            "operation": safe_op,
            "group_by": group_by,
            "agg_column": plan.get("agg_column"),
            "agg_function": plan.get("agg_function", "sum"),
            "sort_by": plan.get("sort_by") or plan.get("agg_column"),
            "sort_order": plan.get("sort_order", "desc"),
            "top_n": plan.get("top_n"),
            "filter_column": plan.get("filter_conditions", [{}])[0].get("column") if plan.get("filter_conditions") else None,
            "filter_value": plan.get("filter_conditions", [{}])[0].get("value") if plan.get("filter_conditions") else None,
        })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json(content: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response, stripping markdown fences."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned an empty response.")

    content = content.strip()

    if content.startswith("```"):
        lines = content.split("\n")
        inner_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner_lines.append(line)
        content = "\n".join(inner_lines)

    return json.loads(content)
