import os
import structlog
from neo4j import AsyncGraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        logger.info("neo4j_driver_created_async")
    return _driver

async def bootstrap_neo4j() -> None:
    """Create structural indexes for SQL schema."""
    driver = _get_driver()
    structural_indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (t:Table)   ON (t.source_id, t.name)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Column)  ON (c.source_id, c.table_name, c.name)",
        "CREATE INDEX IF NOT EXISTS FOR (lib:Library) ON (lib.name)",
    ]
    async with driver.session() as session:
        for q in structural_indexes:
            try:
                await session.run(q)
            except Exception as exc:
                logger.warning("neo4j_index_creation_failed", query=q, error=str(exc))

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    async def close(self) -> None:
        await self.driver.close()

    async def batch_upsert_strategic_schema(self, source_id: str, tables: list[dict], foreign_keys: list[dict] = None) -> None:
        """Sync Enriched SQL Schema to Neo4j with Relationships."""
        foreign_keys = foreign_keys or []
        async with self.driver.session() as session:
            # 1. Upsert Tables
            for table in tables:
                table_name = table["name"]
                await session.run(
                    """
                    MERGE (t:Table {source_id: $source_id, name: $table_name})
                    SET t.summary = $summary,
                        t.row_count = $row_count,
                        t.domain = $domain,
                        t.updated_at = timestamp()
                    """,
                    source_id=source_id,
                    table_name=table_name,
                    summary=table.get("summary", ""),
                    row_count=table.get("row_count"),
                    domain=table.get("domain", "General")
                )
                
                # 2. Upsert Columns
                if "columns" in table:
                    await session.run(
                        """
                        UNWIND $columns AS col
                        MATCH (t:Table {source_id: $source_id, name: $table_name})
                        MERGE (c:Column {source_id: $source_id, table_name: $table_name, name: col.name})
                        SET c.dtype = col.dtype,
                            c.description = col.description,
                            c.archetype = col.archetype,
                            c.sample_values = col.sample_values,
                            c.is_pii = col.is_pii
                        MERGE (t)-[:HAS_COLUMN]->(c)
                        """,
                        source_id=source_id,
                        table_name=table_name,
                        columns=table["columns"]
                    )

            # 3. Upsert Foreign Key Relationships
            for fk in foreign_keys:
                await session.run(
                    """
                    MATCH (t1:Table {source_id: $source_id, name: $from_table})
                    MATCH (t2:Table {source_id: $source_id, name: $to_table})
                    MERGE (t1)-[r:REFERENCES {from_col: $from_col, to_col: $to_col}]->(t2)
                    """,
                    source_id=source_id,
                    from_table=fk["from_table"],
                    from_col=fk["from_col"],
                    to_table=fk["to_table"],
                    to_col=fk["to_col"]
                )

        logger.info("neo4j_strategic_sql_sync_done", source_id=source_id, tables=len(tables))
