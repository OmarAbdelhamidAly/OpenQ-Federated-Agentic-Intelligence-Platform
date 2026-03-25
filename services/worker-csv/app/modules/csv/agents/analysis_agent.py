"""CSV Pipeline — Analysis Agent.

Uses an LLM to generate a pandas-based analysis plan, then dispatches
to the correct CSV tool (compute_trend, compute_correlation, compute_ranking,
or run_pandas_query).

Includes retry logic: up to 3 attempts on failure.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings
from app.modules.csv.tools.load_data_source import resolve_data_path
from app.modules.csv.utils.retrieval import get_kb_context

# ── Prompt ────────────────────────────────────────────────────────────────────

CSV_ANALYSIS_PROMPT = """You are a data analyst. Given the user question, schema, intent, and business metrics dictionary,
write a precise analysis plan as JSON.

Intent values and what tool they map to:
- trend       → use operation "trend" with date_column and value_column
- forecast    → use operation "forecast" with date_column, value_column, periods (default 30)
- correlation → use operation "correlation" with optional columns list
- ranking     → use operation "ranking" with rank_column, label_column, top_n
- comparison  → use operation "groupby" with group_by, agg_column, agg_function
- anomaly     → use operation "trend" (anomaly detection is built-in)
- (default)   → use operation "sort", "filter", "aggregate", or "groupby"

**CRITICAL**: Consult the "Business Metrics Dictionary" to understand company-specific terms. If a metric has a 'formula', try to replicate that logic using the available operations.

Respond ONLY with valid JSON. No explanations. No markdown.

Fields:
{{
  "operation": "groupby|filter|aggregate|sort|pivot|trend|correlation|ranking|forecast",
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

Business Metrics Dictionary:
{metrics}

Schema: {schema}
Question: {question}
Intent: {intent}
Relevant columns: {columns}

{golden_examples}
{complexity_instruction}

Conversational Memory:
{chat_history}

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

    # If this is a retry due to an error, pass the error hint to the model
    error_hint = ""
    if state.get("error"):
        error_hint = f"\n[RETRY HINT] Your previous plan failed with this error: {state['error']}\nPlease fix the logic."
    
    if state.get("policy_violation"):
        error_hint += f"\n[POLICY VIOLATION] Your previous plan was REJECTED for this reason: {state['policy_violation']}\nYou MUST adjust your plan to comply with organization policies."

    llm = get_llm(temperature=0)

    schema_str = _format_compact_schema(state.get("schema_summary", {}))
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
    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    # Retrieve Knowledge Base context if kb_id is present
    kb_context = await get_kb_context(state.get("kb_id"), state["question"])

    # Calculate complexity instructions (Idea: Dynamic reasoning depth)
    idx = state.get("complexity_index", 1)
    tot = state.get("total_pills", 1)
    
    complexity_instruction = ""
    if tot > 1:
        if idx == 1:
            complexity_instruction = "\nCOMPLEXITY LEVEL: 1 (FOUNDATIONAL)\nFocus on a clear, direct answer to the question using basic groupby or filter operations."
        elif idx == tot:
            complexity_instruction = f"\nCOMPLEXITY LEVEL: {idx} (MASTER INSIGHT)\nProvide a sophisticated analysis plan. Combine multiple steps implicitly by choosing the most 'revealing' operation and columns for a strategic overview."
        else:
            complexity_instruction = f"\nCOMPLEXITY LEVEL: {idx} (INVESTIGATIVE)\nLook for deeper patterns or correlations. Don't just answer the question; explore the 'why' by including relevant secondary columns in your analysis."

    history_arr = state.get("history", [])
    chat_history = "No previous conversational context."
    if history_arr:
        chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

    prompt = CSV_ANALYSIS_PROMPT.format(
        metrics=metrics_str,
        schema=schema_str,
        question=state["question"],
        intent=intent,
        columns=columns,
        kb_context=kb_context or "No relevant document context found.",
        golden_examples="No relevant examples found.", # CSV golden logic can be added later
        complexity_instruction=complexity_instruction,
        chat_history=chat_history,
        error_hint=error_hint,
    )

    data_path = resolve_data_path(state)

    # FAST-TRACK: Check if this is a meta-question (schema, columns, rows)
    if not state.get("error") and data_path:
        meta_result = _handle_meta_question(state["question"], state.get("schema_summary", {}), data_path)
        if meta_result:
            return {
                "analysis_results": {
                    "plan": {"operation": "meta_bypass", "summary": "Skipped LLM planner for meta-question"},
                    "source_type": "csv",
                    "dataframe": meta_result["dataframe"].to_dict(orient="records"),
                    "columns": list(meta_result["dataframe"].columns),
                    "summary": meta_result["title"]
                },
                "error": None,
                "retry_count": retry_count,
            }

    # Check if we have a repaired plan from the reflection agent
    repaired_plan = state.get("repaired_plan")
    if repaired_plan:
        plan = repaired_plan
    else:
        response = await llm.ainvoke(prompt)
        plan = _parse_json(response.content)

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
        from app.modules.csv.tools.compute_trend import compute_trend
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

    elif operation == "forecast":
        from app.modules.csv.tools.compute_forecast import compute_forecast
        date_col = plan.get("date_column", "")
        value_col = plan.get("value_column") or plan.get("agg_column", "")
        if not date_col or not value_col:
            raise ValueError("'forecast' operation requires date_column and value_column in the plan.")
        return compute_forecast.invoke({
            "file_path": data_path,
            "date_column": date_col,
            "value_column": value_col,
            "periods": plan.get("periods", 30),
            "freq": plan.get("freq", "D"),
        })

    elif operation == "correlation":
        from app.modules.csv.tools.compute_correlation import compute_correlation
        cols = plan.get("columns") or plan.get("group_by") or None
        if isinstance(cols, str):
            cols = [cols]
        return compute_correlation.invoke({
            "file_path": data_path,
            "columns": cols,
            "method": "pearson",
        })

    elif operation == "ranking":
        from app.modules.csv.tools.compute_ranking import compute_ranking
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
        from app.modules.csv.tools.run_pandas_query import run_pandas_query

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

def _handle_meta_question(question: str, schema: Dict[str, Any], data_path: str) -> Optional[Dict[str, Any]]:
    \"\"\"Answer questions ABOUT the dataset structure directly — no LLM needed.\"\"\"
    import pandas as pd
    q = question.lower().strip()
    columns_info = schema.get("columns", [])
    all_cols = [c["name"] for c in columns_info]
    num_cols = [c["name"] for c in columns_info if "numeric" in c.get("dtype", "").lower() or "int" in c.get("dtype", "").lower() or "float" in c.get("dtype", "").lower()]
    cat_cols = [c["name"] for c in columns_info if "object" in c.get("dtype", "").lower() or "string" in c.get("dtype", "").lower()]
    dt_cols  = [c["name"] for c in columns_info if "datetime" in c.get("dtype", "").lower()]
    n_rows   = schema.get("row_count", 0)

    # How many columns
    if any(p in q for p in ["how many column", "number of column", "count of column", "how many feature", "how many field"]):
        result_df = pd.DataFrame([{
            "total_columns": len(all_cols),
            "numeric_columns": len(num_cols),
            "categorical_columns": len(cat_cols),
            "datetime_columns": len(dt_cols),
        }])
        return {"dataframe": result_df, "title": f"Dataset has {len(all_cols)} columns"}

    # How many rows
    if any(p in q for p in ["how many row", "number of row", "count of row", "how many record", "how many observation", "dataset size", "how big is"]):
        result_df = pd.DataFrame([{
            "total_rows": n_rows,
            "total_columns": len(all_cols),
            "total_cells": schema.get("total_null_cells", 0) + (n_rows * len(all_cols)), # rough estimate
        }])
        return {"dataframe": result_df, "title": f"Dataset has {n_rows:,} rows × {len(all_cols)} columns"}

    # Column list / schema
    if any(p in q for p in ["what are the column", "list column", "show column", "what column", "column name", "show schema", "what fields", "what features", "tell me about the data", "describe the data", "data schema", "show me the schema"]):
        rows = []
        for c in columns_info:
            rows.append({
                "column": c["name"],
                "type": c.get("dtype", "unknown"),
                "unique_values": c.get("unique_count", 0),
                "missing": c.get("null_count", 0),
            })
        return {"dataframe": pd.DataFrame(rows), "title": f"Schema: {len(all_cols)} columns"}

    # Unique values in a specific column
    if any(p in q for p in ["unique value", "distinct value", "unique in", "values in", "what values", "possible value"]):
        target = next((col for col in all_cols if col.lower() in q), None)
        if target:
            try:
                df = pd.read_csv(data_path, usecols=[target])
                unique_vals = df[target].dropna().unique()
                result_df = pd.DataFrame({target: sorted(unique_vals, key=str)})
                return {"dataframe": result_df, "title": f"{len(unique_vals)} unique values in '{target}'"}
            except Exception:
                pass

    # Missing values
    if any(p in q for p in ["missing", "null", "nan", "empty", "incomplete"]):
        rows = []
        for c in columns_info:
            n_miss = c.get("null_count", 0)
            rows.append({
                "column": c["name"],
                "missing_count": n_miss,
                "missing_pct": c.get("null_pct", 0.0),
            })
        result_df = pd.DataFrame(rows).sort_values("missing_count", ascending=False)
        total = result_df["missing_count"].sum()
        return {"dataframe": result_df, "title": f"Missing Values — {total:,} total missing cells"}

    # Summary / overview
    if any(p in q for p in ["summary", "overview", "describe", "summarize", "tell me about", "what is in", "what do we have"]):
        result_df = pd.DataFrame([{
            "rows": n_rows,
            "columns": len(all_cols),
            "numeric_columns": len(num_cols),
            "categorical_columns": len(cat_cols),
            "datetime_columns": len(dt_cols),
            "duplicate_rows": schema.get("duplicate_rows", 0),
        }])
        return {"dataframe": result_df, "title": "Dataset Overview"}

    return None  # Not a meta-question


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


def _format_compact_schema(schema_summary: Dict[str, Any]) -> str:
    """Format the CSV schema summary into a highly compact, token-efficient string."""
    columns = schema_summary.get("columns", [])
    if not columns:
        return json.dumps(schema_summary)
        
    lines = ["Columns & Data Types:"]
    col_strs = []
    for c in columns:
        col_str = f"{c.get('name')} ({c.get('dtype')})"
        if c.get("sample_values"):
            # Truncate samples to just 1 token-friendly example
            samples = [str(s)[:15] for s in c['sample_values'][:1]]
            if samples and samples[0]:
                col_str += f" [eg: {samples[0]}]"
        col_strs.append("- " + col_str)
        
    lines.extend(col_strs)
    return "\n".join(lines)
