"""SQL Pipeline — Analysis Agent.

Uses an LLM to generate a safe SELECT query, then dispatches it
to the run_sql_query tool for parameterized execution.

Includes retry logic: up to 3 attempts on failure.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings
from app.modules.shared.tools.load_data_source import get_connection_string
from app.modules.shared.utils.retrieval import get_kb_context

# ── Prompt ────────────────────────────────────────────────────────────────────

SQL_ANALYSIS_PROMPT = """You are a SQL expert. Given the user question, database schema, and a dictionary of business metrics,
write a safe, read-only SELECT query to answer the question.

Rules:
- Only SELECT queries. No INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Use parameterised query syntax (:param_name) for any user-supplied values.
- Keep results under 1000 rows using LIMIT.
- Use the table and column names exactly as they appear in the schema.
- **CRITICAL**: Use the "Business Metrics Dictionary" to understand how to calculate specific business terms (like 'active user' or 'revenue'). If a metric has a 'formula', use that logic in your SQL.

Respond ONLY with valid JSON:
{{
  "query": "SELECT ... FROM ... WHERE ... LIMIT 100",
  "params": {{}}
}}

Business Metrics Dictionary:
{metrics}

Schema: {schema}
Question: {question}
Intent: {intent}
Relevant columns: {columns}

Knowledge Base Context (if relevant):
{kb_context}

{error_hint}"""


# ── Main Agent ────────────────────────────────────────────────────────────────

# ── ReAct Agent ────────────────────────────────────────────────────────────────

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
import structlog

logger = structlog.get_logger("app.debug.tokens")

REACT_SYSTEM_PROMPT = """You are a SQL expert tasked with generating a high-quality SELECT query.
You have access to a SQL execution tool to verify column names, schema details, or sample data.

PROCESS:
1. Review the Schema and Business Metrics.
2. If you are unsure about a column or join, CALL the `run_sql_query` tool with a LIMIT 5 to test your assumptions.
3. Iterate based on tool results.
4. When you have the final, correct query, respond with a JSON block containing "query" and "params".

RULES:
- ONLY SELECT queries.
- Use parameterised syntax (:param).
- Use the provided Business Metrics logic.
- NO destructive operations.

Current Business Metrics: {metrics}
Knowledge Base Context: {kb_context}
"""

async def analysis_agent(state: AnalysisState) -> Dict[str, Any]:
    """ReAct agent that generates and validates SQL queries iteratively."""
    from app.modules.sql.tools.run_sql_query import run_sql_query
    
    llm = get_llm(temperature=0).bind_tools([run_sql_query])

    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    kb_context = await get_kb_context(state.get("kb_id"), state["question"])
    
    # Base messages
    messages = [
        SystemMessage(content=REACT_SYSTEM_PROMPT.format(metrics=metrics_str, kb_context=kb_context or "None")),
    ]

    # Add History if present
    if state.get("history"):
        for msg in state["history"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(SystemMessage(content=msg["content"])) # Simplified history

    # Add Error/Violation hint if retrying
    error_hint = ""
    if state.get("error"):
        error_hint += f"\n[RETRY HINT] Previous attempt failed: {state['error']}"
    if state.get("policy_violation"):
        error_hint += f"\n[POLICY VIOLATION] Previous attempt rejected: {state['policy_violation']}"

    # Current Request
    compact_schema = _format_compact_schema(state.get('schema_summary', {}))
    messages.append(HumanMessage(content=f"Question: {state['question']}\nSchema:\n{compact_schema}\n{error_hint}"))

    # Simple manual ReAct loop (max 3 turns)
    generated_sql = None
    params = {}
    steps = state.get("intermediate_steps") or []
    
    for turn in range(3):
        response = await llm.ainvoke(messages)
        
        # Log token usage
        if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
            usage = response.response_metadata["token_usage"]
            logger.info("llm_token_usage", prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0), total_tokens=usage.get("total_tokens", 0))

        messages.append(response)
        
        # Capture thought
        if response.content:
            steps.append({"role": "thought", "content": response.content})
        
        if not response.tool_calls:
            try:
                plan = _parse_json(response.content)
                generated_sql = plan.get("query")
                params = plan.get("params", {})
                if generated_sql:
                    break
                else:
                    messages.append(HumanMessage(content="The JSON did not contain a 'query' field. Please provide {'query': '...', 'params': {}}"))
                    continue
            except Exception as e:
                messages.append(HumanMessage(content=f"Could not parse JSON. Error: {str(e)}. Please provide ONLY a valid JSON object: {{'query': '...', 'params': {{}}}}"))
                continue
        
        for tool_call in response.tool_calls:
            if tool_call["name"] == "run_sql_query":
                args = tool_call["args"]
                args["limit"] = 5
                steps.append({"role": "tool_call", "tool": "run_sql_query", "args": args})
                try:
                    tool_output = run_sql_query.invoke(args)
                    steps.append({"role": "tool_result", "content": "Query executed successfully."})
                    messages.append(ToolMessage(content=json.dumps(tool_output), tool_call_id=tool_call["id"]))
                except Exception as e:
                    steps.append({"role": "tool_result", "content": f"Query failed: {str(e)}"})
                    messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call["id"]))

    if not generated_sql:
        return {"error": "Failed to generate a valid SQL query after ReAct iterations.", "intermediate_steps": steps}

    return {
        "generated_sql": generated_sql,
        "analysis_results": {
            "plan": {"query": generated_sql, "params": params},
            "source_type": "sql",
        },
        "intermediate_steps": steps,
        "error": None
    }


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


def _format_compact_schema(schema_summary: Dict[str, Any]) -> str:
    """Format the schema summary into a highly compact, token-efficient string."""
    if not schema_summary.get("tables"):
        return json.dumps(schema_summary)
        
    lines = []
    
    # Include ERD to strictly define joins
    erd = schema_summary.get("mermaid_erd")
    if erd:
        lines.append("Data Relationships (ERD):")
        lines.append(erd)
        lines.append("")
        
    lines.append("Tables & Columns:")
    for t in schema_summary.get("tables", []):
        col_strs = []
        for c in t.get("columns", []):
            col_str = f"{c['name']} ({c['dtype']})"
            if c.get("primary_key"):
                col_str += " PK"
            if c.get("sample_values"):
                # heavily truncate samples to just 1 token-friendly example
                samples = [str(s)[:15] for s in c['sample_values'][:1]]
                if samples and samples[0]:
                    col_str += f" [eg: {samples[0]}]"
            col_strs.append(col_str)
        lines.append(f"- {t['table']}: " + ", ".join(col_strs))
        
    return "\n".join(lines)

