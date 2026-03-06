"""SQL Pipeline — Data Discovery Agent.

Introspects the SQL database via INFORMATION_SCHEMA to build a schema summary.
Uses the sql_schema_discovery tool with the decrypted connection string.
SQL data is assumed to be high quality (score = 1.0).
"""

from __future__ import annotations

from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.modules.shared.tools.load_data_source import get_connection_string


async def data_discovery_agent(state: AnalysisState) -> Dict[str, Any]:
    """Introspect the SQL database, generate ERD, and filter relevant tables."""
    connection_string = get_connection_string(state)
    if not connection_string:
        return {
            "schema_summary": state.get("schema_summary", {}),
            "data_quality_score": 1.0,
        }

    try:
        from app.modules.sql.tools.sql_schema_discovery import sql_schema_discovery

        raw = sql_schema_discovery.invoke({
            "connection_string": connection_string,
            "sample_rows": 1,
        })

        
        from structlog import get_logger
        debug_logger = get_logger("app.debug.erd")
        debug_logger.info("erd_discovery_raw", tables_count=len(raw.get("tables", [])), fks_count=len(raw.get("foreign_keys", [])))


        from app.modules.sql.utils.schema_utils import infer_foreign_keys, generate_mermaid_erd

        # ── 1. Generate Mermaid ERD (Strong Visualization) ──
        tables = raw.get("tables", [])
        foreign_keys = raw.get("foreign_keys", [])
        
        # Infer relationships and generate ERD using shared utility
        final_fks = infer_foreign_keys(tables, foreign_keys)
        mermaid_erd = generate_mermaid_erd(tables, final_fks)
        
        # Update raw with inferred keys for the summary
        raw["foreign_keys"] = final_fks

        # ── 2. Semantic Filtering (RAG Filter) ──
        # If the question is specific, prune irrelevant tables to save context space
        question = state.get("question", "").lower()
        all_tables = raw.get("tables", [])
        
        if len(all_tables) > 10 and question:
            # Simple keyword-based filtering for now (could be upgraded to full embedding-based RAG)
            relevant_tables = []
            for t in all_tables:
                t_name = t["table"].lower()
                # Check if table name or any column name appears in the question
                cols = [c["name"].lower() for c in t["columns"]]
                if any(kw in question for kw in [t_name] + cols):
                    relevant_tables.append(t)
            
            # If we found relevant tables, filter the summary
            if relevant_tables:
                raw["tables"] = relevant_tables
                raw["table_count"] = len(relevant_tables)

        schema_summary = {
            "source_type": "sql",
            "mermaid_erd": mermaid_erd,
            **raw,
        }

        return {
            "schema_summary": schema_summary,
            "data_quality_score": 1.0,
        }

    except Exception as exc:
        # Non-fatal: return empty schema, pipeline continues
        return {
            "schema_summary": {
                "source_type": "sql",
                "error": str(exc),
                "tables": [],
            },
            "data_quality_score": 1.0,
        }
