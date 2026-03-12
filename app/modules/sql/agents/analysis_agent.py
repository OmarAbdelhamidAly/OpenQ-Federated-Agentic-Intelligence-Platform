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
from app.modules.sql.utils.sql_validator import SQLValidator
from app.modules.sql.tools.run_sql_query import get_async_engine
from app.modules.sql.utils.golden_sql import golden_sql_manager
from app.modules.sql.utils.schema_selector import schema_selector
from app.modules.sql.utils.schema_mapper import schema_mapper
from app.modules.sql.utils.insight_memory import insight_memory

# ── Prompt ────────────────────────────────────────────────────────────────────

SQL_ANALYSIS_PROMPT = """You are a SQL expert. Given the user question, database schema, and a dictionary of business metrics,
write a safe, read-only SELECT query to answer the question.

Rules:
- Only SELECT queries. No INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Use parameterised query syntax (:param_name) for any user-supplied values.
- Keep results under 1000 rows using LIMIT.
- Use the table and column names exactly as they appear in the schema.
- **CRITICAL**: Use the "Business Metrics Dictionary" as the primary definition for terms. If a metric exists there, use its 'formula'. DO NOT guess or use hardcoded assumptions if a metric is provided.
- For joins, always refer to the Data Relationships (ERD) provided.

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
1. Review the Schema, Business Metrics, and reference "Golden SQL" examples.
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

GOLDEN SQL EXAMPLES (References):
{golden_examples}

VALIDATION FEEDBACK:
If the `run_sql_query` tool or the validator returns errors, you MUST fix them in the next turn.
Always use "EXPLAIN" (via tool call) if you are uncertain about a schema path.

REFLECTION GUIDANCE:
If `reflection_context` is provided, it means your previous query returned 0 rows. 
Analyze the schema and sample values to understand why. For example, if you filtered by '2024' but samples show only '2023', adjust your query to be more relevant.
"""

async def analysis_agent(state: AnalysisState) -> Dict[str, Any]:
    """ReAct agent that generates and validates SQL queries iteratively."""
    from app.modules.sql.tools.run_sql_query import run_sql_query
    
    llm = get_llm(temperature=0).bind_tools([run_sql_query])

    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    kb_context = await get_kb_context(state.get("kb_id"), state["question"])
    
    # Fetch Golden SQL examples (Idea 8)
    goldens = golden_sql_manager.get_similar_examples(state["question"])
    golden_str = "\n".join([f"Q: {ex['question']}\nSQL: {ex['sql']}" for ex in goldens]) if goldens else "No relevant examples found."

    # Base messages
    messages = [
        SystemMessage(content=REACT_SYSTEM_PROMPT.format(
            metrics=metrics_str, 
            kb_context=kb_context or "None",
            golden_examples=golden_str
        )),
    ]

    # Add History if present
    if state.get("history"):
        for msg in state["history"]:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                # Ensure the LLM recognizes its own previous SQL generations
                messages.append(SystemMessage(content=f"PREVIOUS_TURN_SQL: {content}"))

    # Add Error/Violation hint if retrying
    error_hint = ""
    if state.get("error"):
        error_hint += f"\n[RETRY HINT] Previous attempt failed: {state['error']}"
    if state.get("policy_violation"):
        error_hint += f"\n[POLICY VIOLATION] Previous attempt rejected: {state['policy_violation']}"
    if state.get("reflection_context"):
        error_hint += f"\n[REFLECTION] {state['reflection_context']}"
    if state.get("user_feedback"):
        error_hint += f"\n[USER FEEDBACK] The user requested a refinement: {state['user_feedback']}"

    # Current Request
    full_schema = state.get('schema_summary', {})
    relevant_schema = schema_selector.select_tables(full_schema, state["question"])
    
    # Apply business metadata (Idea 15)
    mapped_schema = schema_mapper.map_schema(relevant_schema)
    compact_schema = _format_compact_schema(mapped_schema)
    
    # Retrieve historical context (Idea 16)
    past_insights = insight_memory.get_related_insights(state["question"])
    history_str = ""
    if past_insights:
        history_str = "\nRelevant Past Analyses:\n" + "\n".join([f"- Q: {i['question']} -> SQL: {i['sql']}" for i in past_insights])

    # Validation Warnings (Idea 7)
    perf_hint = ""
    validation_results = state.get("validation_results")
    if validation_results and validation_results.get("warnings"):
        perf_hint = "\nOptimization Warning: " + "; ".join(validation_results["warnings"])

    messages.append(HumanMessage(content=f"Question: {state['question']}\n{history_str}\nSchema:\n{compact_schema}\n{error_hint}{perf_hint}"))

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
                    tool_output = await run_sql_query.ainvoke(args)
                    steps.append({"role": "tool_result", "content": "Query executed successfully."})
                    messages.append(ToolMessage(content=json.dumps(tool_output), tool_call_id=tool_call["id"]))
                except Exception as e:
                    steps.append({"role": "tool_result", "content": f"Query failed: {str(e)}"})
                    messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call["id"]))

    if not generated_sql:
        return {"error": "Failed to generate a valid SQL query after ReAct iterations.", "intermediate_steps": steps}

    # ── Final Validation Check ──
    # One last verification using the 3-layer validator before exiting.
    connection_string = get_connection_string(state)
    engine = get_async_engine(connection_string) if connection_string else None
    validator = SQLValidator(engine, state.get("schema_summary"))
    
    validation = await validator.validate(generated_sql)
    if not validation["valid"]:
        # If the final query is STILL invalid, return the error to trigger a Graph retry
        return {
            "error": f"Post-generation validation failed: {'; '.join(validation['errors'])}",
            "intermediate_steps": steps,
            "validation_results": validation
        }

    return {
        "generated_sql": generated_sql,
        "validation_results": validation,
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
    """Format the schema summary into an ultra-dense, token-saving string."""
    if not schema_summary.get("tables"):
        return "{}"
        
    lines = []
    
    # 1. Relationships (Essential for Joins)
    erd = schema_summary.get("mermaid_erd")
    if erd:
        # Keep ERD as is, it's already a very dense representation of relationships
        lines.append("Relationships:")
        lines.append(erd.replace("erDiagram", "").strip())
        lines.append("")
        
    # 2. Tables & Columns (High-Density)
    lines.append("Definition (table: col(type) [eg: sample] {desc}):")
    for t in schema_summary.get("tables", []):
        col_parts = []
        t_desc = f" {{{t['description']}}}" if t.get("description") else ""
        
        for c in t.get("columns", []):
            # Use shorthand: * for PK, type in parens
            label = f"{c['name']}({c['dtype']})"
            if c.get("primary_key"):
                label += "*"
            
            # Smart sample pruning: only show if strictly useful and keep it short
            samples = c.get("sample_values", [])
            if samples and samples[0] and len(str(samples[0])) > 0:
                s = str(samples[0])[:12] # Keep it very short
                label += f"[{s}]"
            
            # Add business description (Idea 15)
            if c.get("description"):
                label += f" <{c['description']}>"
            
            col_parts.append(label)
        
        lines.append(f"- {t['table']}{t_desc}: {', '.join(col_parts)}")
        
    return "\n".join(lines)

