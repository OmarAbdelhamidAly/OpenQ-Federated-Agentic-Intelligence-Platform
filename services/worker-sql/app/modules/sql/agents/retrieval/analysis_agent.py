"""SQL Pipeline — Analysis Agent.

Uses an LLM to generate a safe SELECT query, then dispatches it
to the run_sql_query tool for parameterized execution.

Includes retry logic: up to 3 attempts on failure.
"""

from __future__ import annotations

import json
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings
from app.modules.sql.tools.load_data_source import get_connection_string
from app.modules.sql.utils.retrieval import get_kb_context
from app.modules.sql.utils.sql_validator import SQLValidator
from app.modules.sql.tools.run_sql_query import get_async_engine
from app.modules.sql.utils.insight_memory import episodic_memory
from app.modules.sql.utils.procedural_memory import procedural_memory
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

# ── Prompt ────────────────────────────────────────────────────────────────────

REACT_SYSTEM_PROMPT = """You are an expert SQL analyst. 
Use the provided tools to explore the database and generate an accurate SQL query.
Follow the ReAct pattern: Thought, Action, Observation.

{complexity_instruction}

Business Metrics:
{metrics}

Reference Context:
{kb_context}

Golden Examples:
{golden_examples}

Conversational Memory:
{running_summary}
{chat_history}

Procedural Skill:
{procedural_skill}

{error_hint}

Final Answer format must be JSON: {{"query": "SELECT ...", "params": {{}}}}

IMPORTANT: Be extremely concise. Avoid unnecessary preamble. 
If hitting rate limits, the system will retry, but smaller prompts/responses are faster.
"""

SQLCODER_TEMPLATE = """### Task
Generate a SQL query to answer the user question.
- Only SELECT queries are allowed.
- Use parameterised syntax (:param_name) for any filters.
- Use the provided database schema to understand relationships.
- Use the Business Metrics formula if defined.

### Business Metrics
{metrics}

### Database Schema
The following is the DDL for the tables relevant to the question:
{schema}

### Reference Context
Knowledge Base: {kb_context}
Golden Examples: {golden_examples}

### Question
{question}

### Answer
"""

# ... (rest of the file remains similar but uses the new DDL format in compact_schema)

def _format_ddl_schema(schema_summary: Dict[str, Any]) -> str:
    """Format the schema summary into standard DDL (CREATE TABLE) statements."""
    if not schema_summary.get("tables"):
        return "{}"
        
    ddl_statements = []
    
    for t in schema_summary.get("tables", []):
        table_name = t['table']
        columns = []
        for c in t.get("columns", []):
            col_def = f"  {c['name']} {c['dtype']}"
            if c.get("primary_key"):
                col_def += " PRIMARY KEY"
            if c.get("description"):
                col_def += f" -- {c['description']}"
            columns.append(col_def)
        
        # Add foreign keys if available in metadata
        # (Assuming relationships are stored or derived from mermaid_erd)
        
        ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(columns) + "\n);"
        ddl_statements.append(ddl)
        
    # Append Mermaid ERD as a high-level overview if it helps
    erd = schema_summary.get("mermaid_erd")
    if erd:
        ddl_statements.append(f"\n/* Relationships Overview (Mermaid):\n{erd}\n*/")
        
    return "\n\n".join(ddl_statements)

# ... (I'll apply these changes to the actual file content now)

async def analysis_agent(state: AnalysisState) -> Dict[str, Any]:
    """ReAct agent that generates and validates SQL queries iteratively."""
    from app.modules.sql.tools.run_sql_query import run_sql_query

    # ── Fix 4: Guard against empty schema ──────────────────────────────────────
    # If data_discovery_agent failed to load any table info (e.g. wrong file
    # path, failed connection), the LLM has nothing to work with and will
    # hallucinate non-existent tables/columns → silent 0-row results.
    # Fail fast here with a clear error instead.
    schema_summary = state.get("schema_summary", {})
    if not schema_summary.get("tables"):
        schema_error = schema_summary.get("error", "No tables found in the database schema.")
        logger.error(
            "analysis_agent_aborted_empty_schema",
            schema_error=schema_error,
            file_path=state.get("file_path"),
        )
        return {
            "error": (
                f"Schema discovery returned no tables: {schema_error}. "
                "Check that the data source file_path is correct and the file exists."
            )
        }
    # ── FAST-TRACK: Check for Meta-Questions (Schema/Structural) ────────────────
    meta_result = _handle_meta_question(state["question"], schema_summary)
    if meta_result:
        return {
            "analysis_results": {
                "plan": {"query": "meta_bypass", "summary": "Skipped LLM for structural question"},
                "source_type": "sql",
                "data": meta_result["dataframe"].to_dict(orient="records"),
                "summary": meta_result["title"]
            },
            "error": None,
            "intermediate_steps": [{"role": "thought", "content": "Meta-question detected. Bypassing LLM."}]
        }
    # ───────────────────────────────────────────────────────────────────────────

    # Currently using Groq/Llama-8b for free tier speed.
    # To upgrade accuracy, swap to the specialized SQL model below:
    # llm = get_llm(temperature=0, model="defog/sqlcoder-70b-v2").bind_tools([run_sql_query])
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_SQL).bind_tools([run_sql_query])

    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    kb_context = await get_kb_context(state.get("kb_id"), state["question"])
    
    # Fetch Golden SQL examples (Idea 8)
    goldens = golden_sql_manager.get_similar_examples(state["question"])
    golden_str = "\n".join([f"Q: {ex['question']}\nSQL: {ex['sql']}" for ex in goldens]) if goldens else "No relevant examples found."

    # Calculate complexity instructions (Idea: Dynamic reasoning depth)
    idx = state.get("complexity_index", 1)
    tot = state.get("total_pills", 1)
    
    complexity_instruction = ""
    if tot > 1:
        if idx == 1:
            complexity_instruction = "\nCOMPLEXITY LEVEL: 1 (FOUNDATIONAL)\nFocus on a clear, direct answer to the question using standard aggregations."
        elif idx == tot:
            complexity_instruction = f"\nCOMPLEXITY LEVEL: {idx} (MASTER INSIGHT)\nThis is the final analysis in the sequence. Provide a sophisticated, multi-dimensional query. Incorporate advanced logic or CTEs if needed to provide a 'grand finale' insight."
        else:
            complexity_instruction = f"\nCOMPLEXITY LEVEL: {idx} (ADVANCED)\nGo beyond the surface. Look for correlations or deeper trends related to the question. Use multi-table JOINS and complex filters if appropriate."

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

    # Prepare chat history for conversational memory
    history_arr = state.get("history", [])
    chat_history = "No previous conversational context."
    if history_arr:
        chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

    # Base messages
    messages = [
        SystemMessage(content=REACT_SYSTEM_PROMPT.format(
            metrics=metrics_str, 
            kb_context=kb_context or "None",
            golden_examples=golden_str,
            complexity_instruction=complexity_instruction,
            running_summary=state.get("running_summary", "No previous context."),
            chat_history=chat_history,
            procedural_skill=procedural_memory.get_procedural_knowledge(state.get("intent", "trend")),
            error_hint=error_hint
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
                messages.append(HumanMessage(content=f"PREVIOUS_TURN_SQL: {content}"))

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
    ddl_schema = _format_ddl_schema(mapped_schema)
    
    # Retrieve historical context (Episodic Memory)
    past_insights = await episodic_memory.get_related_insights(state["tenant_id"], state["question"])
    history_str = ""
    if past_insights:
        history_str = "\nRelevant Past Analyses:\n" + "\n".join([f"- Q: {i['question']} -> SQL: {i['sql']}" for i in past_insights])

    # Validation Warnings (Idea 7)
    perf_hint = ""
    validation_results = state.get("validation_results")
    if validation_results and validation_results.get("warnings"):
        perf_hint = "\nOptimization Warning: " + "; ".join(validation_results["warnings"])

    messages.append(HumanMessage(content=SQLCODER_TEMPLATE.format(
        metrics=metrics_str,
        schema=ddl_schema,
        kb_context=kb_context or "None",
        golden_examples=golden_str,
        question=state["question"]
    )))

    if error_hint or perf_hint:
        messages.append(HumanMessage(content=f"IMPORTANT FEEDBACK:\n{error_hint}\n{perf_hint}"))
      # Simple manual ReAct loop (max 3 turns)
    generated_sql = None
    params = {}
    steps = state.get("intermediate_steps") or []
    
    for turn in range(3):  # 3 turns for lean reasoning
        response = await llm.ainvoke(messages)
        
        # Log token usage
        if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
            usage = response.response_metadata["token_usage"]
            logger.info("llm_token_usage", prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0), total_tokens=usage.get("total_tokens", 0))

        logger.info("llm_raw_response", content=response.content, tool_calls=response.tool_calls)
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
                logger.error("json_parse_failed", error=str(e), content=response.content)
                messages.append(HumanMessage(content=f"Could not parse JSON. Error: {str(e)}. Please provide ONLY a valid JSON object: {{'query': '...', 'params': {{}}}}"))
                continue
        
        for tool_call in response.tool_calls:
            if tool_call["name"] == "run_sql_query":
                args = tool_call["args"]
                # Hard override to prevent hallucination
                args["connection_string"] = get_connection_string(state)
                args["limit"] = 5
                
                # Internal execution (Idea: don't pollute LLM history with secret connection strings)
                clean_args = {k: v for k, v in args.items() if k != "connection_string"}
                steps.append({"role": "tool_call", "tool": "run_sql_query", "args": clean_args})
                
                try:
                   from app.modules.sql.tools.run_sql_query import _run_sql_query_internal
                   tool_output = await _run_sql_query_internal(**args)
                   steps.append({"role": "tool_result", "content": "Query executed successfully."})
                   
                   # Pass clean_args back in the ToolMessage to keep LLM's context clean
                   messages.append(ToolMessage(
                       content=json.dumps(tool_output), 
                       name=tool_call["name"],
                       tool_call_id=tool_call["id"]
                   ))
                except Exception as e:
                   steps.append({"role": "tool_result", "content": f"Query failed: {str(e)}"})
                   messages.append(ToolMessage(
                       content=f"Error: {str(e)}", 
                       name=tool_call["name"],
                       tool_call_id=tool_call["id"]
                   ))

    if not generated_sql:
        logger.warning("sql_generation_failed_after_react", job_id=state.get("thread_id"))
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

def _handle_meta_question(question: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Answer questions ABOUT the database structure directly — no LLM needed."""
    import pandas as pd
    q = question.lower().strip()
    tables = schema.get("tables", [])
    
    # 1. Table Count
    if any(p in q for p in ["how many table", "number of table", "count of table", "list of table", "what tables"]):
        rows = [{"table_name": t["table"], "description": t.get("description", "N/A")} for t in tables]
        result_df = pd.DataFrame(rows)
        return {"dataframe": result_df, "title": f"Database has {len(tables)} tables"}

    # 2. Specific Table Structure
    # Check if a table name from the schema is mentioned in the query
    target_table = next((t["table"] for t in tables if t["table"].lower() in q), None)
    if target_table and any(p in q for p in ["columns in", "fields in", "schema of", "describe", "what is in", "tell me about"]):
        t_info = next(t for t in tables if t["table"] == target_table)
        rows = [{"column": c["name"], "type": c.get("dtype", "unknown"), "description": c.get("description", "")} for c in t_info["columns"]]
        result_df = pd.DataFrame(rows)
        return {"dataframe": result_df, "title": f"Schema for table '{target_table}'"}

    # 3. ERD / Relationships
    if any(p in q for p in ["relationship", "erd", "diagram", "how is it connected", "linked"]):
        erd = schema.get("mermaid_erd", "No relationship diagram available.")
        result_df = pd.DataFrame([{"mermaid_erd": erd}])
        return {"dataframe": result_df, "title": "Database Relationship Overview"}

    return None


def _parse_json(content: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response, handling markers or raw text."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned an empty response.")

    content = content.strip()

    # 1. Try finding JSON within markdown code blocks
    if "```json" in content:
        content = content.split("```json")[-1].split("```")[0].strip()
    elif "```" in content:
        # If there are multiple blocks, try the last one
        blocks = content.split("```")
        if len(blocks) >= 3:
            content = blocks[-2].strip()
        else:
            content = blocks[1].strip()
    
    # 2. Heuristic: Find the first '{' and last '}'
    start_idx = content.find('{')
    end_idx = content.rfind('}')
    if start_idx != -1 and end_idx != -1:
        json_str = str(content[start_idx : end_idx + 1])
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass # Fall back to full content parse if substring fails

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

