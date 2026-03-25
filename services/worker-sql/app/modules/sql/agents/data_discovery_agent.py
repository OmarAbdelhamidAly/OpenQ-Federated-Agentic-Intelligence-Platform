"""SQL Pipeline — Data Discovery Agent.

Introspects the SQL database via INFORMATION_SCHEMA to build a schema summary.
Uses the sql_schema_discovery tool with the decrypted connection string.
SQL data is assumed to be high quality (score = 1.0).
"""

from __future__ import annotations

from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.modules.sql.tools.load_data_source import get_connection_string


async def data_discovery_agent(state: AnalysisState) -> Dict[str, Any]:
    """Introspect the SQL database, generate ERD, and return FULL schema.

    Strategy (fastest → most complete):
    1. If the state already has a schema_summary with tables (passed from the
       governance layer from the DataSource.schema_json stored in PostgreSQL),
       enrich it with a Mermaid ERD and return immediately — no new DB call.
    2. If not, fall back to live sql_schema_discovery from the connection.

    This prevents 0-row results caused by:
    - The re-discovery connection failing silently → empty schema → LLM hallucinates
    - SQLite lock issues when multiple jobs hit the same file simultaneously
    """
    from structlog import get_logger
    _log = get_logger("sql.data_discovery")

    # ── Strategy 1: Reuse pre-profiled schema from DB (fast path) ─────────────
    cached_schema = state.get("schema_summary", {})
    if cached_schema.get("tables"):
        _log.info(
            "data_discovery_using_cached_schema",
            table_count=len(cached_schema["tables"]),
        )
        # Enrich with Mermaid ERD if not already present
        if not cached_schema.get("mermaid_erd"):
            from app.modules.sql.utils.schema_utils import infer_foreign_keys, generate_mermaid_erd
            tables = cached_schema.get("tables", [])
            fks = cached_schema.get("foreign_keys", [])
            final_fks = infer_foreign_keys(tables, fks)
            mermaid_erd = generate_mermaid_erd(tables, final_fks)
            cached_schema = {
                **cached_schema,
                "foreign_keys": final_fks,
                "mermaid_erd": mermaid_erd,
                "source_type": cached_schema.get("source_type", "sql"),
            }
        return {
            "schema_summary": cached_schema,
            "data_quality_score": 1.0,
        }

    # ── Strategy 2: Live discovery ─────────────────────────────────────────────
    _log.info("data_discovery_live_connection", file_path=state.get("file_path"))
    connection_string = get_connection_string(state)
    if not connection_string:
        return {
            "schema_summary": state.get("schema_summary", {}),
            "data_quality_score": 1.0,
        }

    try:
        from app.modules.sql.tools.sql_schema_discovery import sql_schema_discovery

        # force_refresh=True to bust stale cache and always get real schema
        raw = sql_schema_discovery.invoke({
            "connection_string": connection_string,
            "sample_rows": 3,
            "force_refresh": True,
        })

        _log.info(
            "erd_discovery_raw",
            tables_count=len(raw.get("tables", [])),
            fks_count=len(raw.get("foreign_keys", [])),
        )

        from app.modules.sql.utils.schema_utils import infer_foreign_keys, generate_mermaid_erd

        tables = raw.get("tables", [])
        foreign_keys = raw.get("foreign_keys", [])
        final_fks = infer_foreign_keys(tables, foreign_keys)
        mermaid_erd = generate_mermaid_erd(tables, final_fks)
        raw["foreign_keys"] = final_fks

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
        _log.error("data_discovery_live_failed", error=str(exc))
        return {
            "schema_summary": {
                "source_type": "sql",
                "error": str(exc),
                "tables": [],
            },
            "data_quality_score": 1.0,
        }

