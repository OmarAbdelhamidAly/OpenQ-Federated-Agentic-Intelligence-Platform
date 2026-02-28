"""SQL Pipeline — Data Discovery Agent.

Introspects the SQL database via INFORMATION_SCHEMA to build a schema summary.
Uses the sql_schema_discovery tool with the decrypted connection string.
SQL data is assumed to be high quality (score = 1.0).
"""

from __future__ import annotations

from typing import Any, Dict

from app.agents.state import AnalysisState
from app.tools.load_data_source import get_connection_string


async def data_discovery_agent(state: AnalysisState) -> Dict[str, Any]:
    """Introspect the SQL database and return a schema summary.

    Always assigns data_quality_score = 1.0 for SQL sources — the database
    manages its own data integrity and we don't attempt to clean it.
    """
    connection_string = get_connection_string(state)
    if not connection_string:
        # Fallback: return whatever is already in state (pre-populated schema)
        return {
            "schema_summary": state.get("schema_summary", {}),
            "data_quality_score": 1.0,
        }

    try:
        from app.tools.sql.sql_schema_discovery import sql_schema_discovery

        raw = sql_schema_discovery.invoke({
            "connection_string": connection_string,
            "sample_rows": 3,
        })

        schema_summary = {
            "source_type": "sql",
            **raw,
        }

        return {
            "schema_summary": schema_summary,
            "data_quality_score": 1.0,  # SQL DBs manage their own quality
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
