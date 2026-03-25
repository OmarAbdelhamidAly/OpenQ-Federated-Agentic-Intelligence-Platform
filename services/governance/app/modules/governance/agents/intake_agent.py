"""Intake agent — parses the user's question, determines intent and relevant columns."""
from __future__ import annotations
import json
import re
import structlog
from typing import Any, Dict
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

INTAKE_PROMPT = """You are a Senior Strategic Intake Analyst for an enterprise data platform.
Your goal is to deconstruct the user's natural language question into a structured execution plan.

Given a user's question, a data source schema, and a dictionary of business metrics, determine:
1. **intent**: The analytical pattern required. (trend, comparison, ranking, correlation, anomaly, greeting, identity)
2. **relevant_columns**: List of specific column names from the schemas required.
3. **required_pillars**: List of data pillars required to answer (e.g., ["sql", "pdf", "csv"]).
4. **time_range**: Extract specific periods if mentioned.
5. **clarification_needed**: Request more info if vague. If intent is 'greeting' or 'identity', provide a friendly, dynamic conversational response acting as OpenQ.AI (an autonomous AI data platform) based on the context.

Respond in the following STRICT JSON format:
{{
  "intent": "...",
  "relevant_columns": ["col1", "col2"],
  "required_pillars": ["pillarA", "pillarB"],
  "time_range": null,
  "clarification_needed": null
}}

STRICT JSON format only. NO PREAMBLE. NO post-explanation.

Business Metrics Dictionary:
{metrics}

Schema:
{schema}

Conversational Memory:
{chat_history}

User Question: {question}"""

def _get_optimized_schema(schema: Dict[str, Any], max_chars: int = 18000) -> str:
    """Returns a rich but compact schema representation."""
    lines = []
    tables = schema.get("tables", [])
    
    if isinstance(tables, dict):
        items = tables.items()
    else:
        items = [(t.get("table", "unknown"), t) for t in tables]

    for table_name, table_info in items:
        table_desc = f" [{table_info['description']}]" if table_info.get("description") else ""
        lines.append(f"Table {table_name}{table_desc}:")
        
        for col in table_info.get("columns", []):
            name = col.get("name")
            dtype = col.get("dtype", "unknown")
            desc = f" -- {col['description']}" if col.get("description") else ""
            pk = " (PK)" if col.get("primary_key") else ""
            fk = f" (FK -> {col['foreign_key']})" if col.get("foreign_key") else ""
            
            line = f"  - {name} ({dtype}){pk}{fk}{desc}"
            lines.append(line)
        
        lines.append("")
        if len("\n".join(lines)) > max_chars:
            lines.append("... [Schema truncated]")
            break
            
    return "\n".join(lines)

async def intake_agent(state: AnalysisState) -> Dict[str, Any]:
    llm = get_llm(temperature=0)
    
    # Build collective schema from one or multiple sources
    schemas_to_analyze = []
    selected_sources = state.get("selected_sources", [])
    
    if selected_sources:
        for idx, src in enumerate(selected_sources):
            schemas_to_analyze.append(f"Source {idx+1} [Type: {src['type']}, Name: {src['name']}]:")
            schemas_to_analyze.append(_get_optimized_schema(src.get("schema", {})))
            schemas_to_analyze.append("-" * 20)
    else:
        # Fallback to single primary source if selected_sources is empty
        schema_summary = state.get("schema_summary", {})
        schemas_to_analyze.append(_get_optimized_schema(schema_summary))
    
    rich_schema = "\n".join(schemas_to_analyze)
    
    history_arr = state.get("history", [])
    chat_history = "No previous conversational context."
    if history_arr:
        chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])
        
    metrics_str = json.dumps(state.get("business_metrics", []), indent=2)
    
    prompt = INTAKE_PROMPT.format(
        metrics=metrics_str, 
        schema=rich_schema, 
        chat_history=chat_history,
        question=state["question"]
    )
    
    try:
        res = await llm.ainvoke(prompt)
        content = res.content
        
        parsed = _parse_json(content)
        
        intent = parsed.get("intent", "comparison")
        
        if intent in ["greeting", "identity"]:
            msg = parsed.get("clarification_needed", "Hello! I am OpenQ.AI, your autonomous data intelligence platform.")
            return {
                "intent": intent,
                "relevant_columns": [],
                "time_range": None,
                "clarification_needed": msg,
            }
            
        return {
            "intent": intent,
            "relevant_columns": parsed.get("relevant_columns", []),
            "required_pillars": parsed.get("required_pillars", [state.get("source_type")]),
            "time_range": parsed.get("time_range"),
            "clarification_needed": parsed.get("clarification_needed"),
        }
    except Exception as e:
        logger.error("intake_agent_failed", error=str(e))
        return {
            "intent": "comparison",
            "relevant_columns": [],
            "time_range": None,
            "clarification_needed": "I encountered an error analyzing your request. Could you please rephrase?",
        }


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
