"""Strategic SQL Profiler Agent.
Enriches raw SQL metadata with business context and domain archetypes via LLM.
"""
import uuid
import structlog
import json
from typing import Dict, Any, List

from app.infrastructure.llm import get_llm
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.database.postgres import async_session_factory
from app.modules.sql.utils.schema_utils import _profile_sqlite
from app.modules.sql.utils.taxonomy import SQL_DOMAINS, COLUMN_ARCHETYPES
from app.models.data_source import DataSource
from sqlalchemy import update, select

logger = structlog.get_logger(__name__)

async def strategic_sql_profiler(source_id: str) -> Dict[str, Any]:
    """Profiles a SQL source and performs semantic enrichment for the Knowledge Graph."""
    logger.info("strategic_sql_profiling_started", source_id=source_id)
    
    # 1. Extract Raw Metadata
    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source: return {"error": "Source not found"}
        file_path = source.file_path

    if not file_path or not os.path.exists(file_path):
        return {"error": "SQLite file not found"}
    
    # Raw profiling (Table names, columns, samples)
    raw_schema = _profile_sqlite(file_path)
    
    # 2. Semantic Enrichment (LLM Pass)
    llm = get_llm(temperature=0)
    
    # Prepare a compact schema for the LLM context
    compact_schema = []
    for t in raw_schema["tables"]:
        t_info = {
            "name": t["table"],
            "row_count": t["row_count"],
            "columns": [{"name": c["name"], "type": c["dtype"], "sample": c["sample_values"][0] if c["sample_values"] else ""} for c in t["columns"]]
        }
        compact_schema.append(t_info)

    enrichment_prompt = f"""
    You are a Strategic Data Architect. Analyze the SQL schema provided below.
    Your goal is to explain what this data represents in a business context to help a Cross-Pillar Orchestrator (Nexus) understand it.
    
    DOMAINS: {json.dumps(SQL_DOMAINS)}
    ARCHETYPES: {json.dumps(COLUMN_ARCHETYPES)}
    
    SCHEMA:
    {json.dumps(compact_schema, indent=2)}
    
    Respond with a strictly formatted JSON object:
    {{
       "tables": [
          {{
             "name": "table_name",
             "domain": "CRM/FINANCE/etc",
             "summary": "Business description of what this table stores"
          }}
       ],
       "columns": [
          {{
             "table": "table_name",
             "name": "col_name",
             "description": "Natural language explanation of this data",
             "archetype": "IDENTIFIER/PII/METRIC/etc",
             "is_pii": true/false
          }}
       ]
    }}
    """
    
    try:
        from langchain_core.output_parsers import JsonOutputParser
        res = await llm.ainvoke(enrichment_prompt)
        mapping = res.content
        if "```json" in mapping:
            mapping = mapping.split("```json")[1].split("```")[0].strip()
        enrichment = json.loads(mapping)
    except Exception as e:
        logger.warning("strategic_enrichment_failed", error=str(e))
        enrichment = {"tables": [], "columns": []}

    # 3. Merge Raw + Enriched Data
    enriched_tables = []
    enrichment_map_tables = {t["name"]: t for t in enrichment.get("tables", [])}
    enrichment_map_cols = {(c["table"], c["name"]): c for c in enrichment.get("columns", [])}
    
    for t in raw_schema["tables"]:
        t_name = t["table"]
        t_enrich = enrichment_map_tables.get(t_name, {})
        
        table_meta = {
            "name": t_name,
            "summary": t_enrich.get("summary", ""),
            "domain": t_enrich.get("domain", "General"),
            "row_count": t["row_count"],
            "columns": []
        }
        
        for c in t["columns"]:
            c_name = c["name"]
            c_enrich = enrichment_map_cols.get((t_name, c_name), {})
            table_meta["columns"].append({
                "name": c_name,
                "dtype": c["dtype"],
                "description": c_enrich.get("description", ""),
                "archetype": c_enrich.get("archetype", "Unknown"),
                "is_pii": c_enrich.get("is_pii", False),
                "sample_values": c["sample_values"]
            })
        enriched_tables.append(table_meta)

    # 4. Sync to Knowledge Graph (Neo4j)
    neo4j = Neo4jAdapter()
    await neo4j.batch_upsert_strategic_schema(
        source_id=source_id,
        tables=enriched_tables,
        foreign_keys=raw_schema.get("foreign_keys", [])
    )

    # 5. Update DataSource Status
    async with async_session_factory() as db:
        final_schema = {**raw_schema, "enriched": True, "tables": enriched_tables}
        await db.execute(
            update(DataSource).where(DataSource.id == uuid.UUID(source_id))
            .values(indexing_status="done", schema_json=final_schema)
        )
        await db.commit()

    logger.info("strategic_sql_profiling_complete", source_id=source_id, tables=len(enriched_tables))
    return {"status": "success", "tables": len(enriched_tables)}

import os
