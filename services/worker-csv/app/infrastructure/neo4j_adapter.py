import os
import structlog
from neo4j import AsyncGraphDatabase
from app.infrastructure.config import settings
import asyncio

logger = structlog.get_logger(__name__)

_driver = None
_loop = None

def _get_driver():
    global _driver, _loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        if _driver is None:
            _driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            )
        return _driver

    if _driver is None or _loop != current_loop:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
        )
        _loop = current_loop
    return _driver

async def bootstrap_neo4j() -> None:
    driver = _get_driver()
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (d:Dataset) ON (d.source_id)",
        "CREATE INDEX IF NOT EXISTS FOR (c:DatasetColumn) ON (c.source_id, c.name)",
    ]
    async with driver.session() as session:
        for q in indexes:
            try:
                await session.run(q)
            except Exception as exc:
                logger.warning("csv_neo4j_index_failed", query=q, error=str(exc))
    logger.info("csv_neo4j_bootstrap_complete")

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    async def close(self) -> None:
        await self.driver.close()

    async def upsert_dataset_schema(self, source_id: str, df_profile: dict) -> None:
        columns = df_profile.get("columns", [])
        dataset_name = df_profile.get("name", "Unknown_Dataset")
        
        async with self.driver.session() as session:
            # 1. Create Dataset Node
            await session.run(
                """
                MERGE (d:Dataset {source_id: $source_id})
                ON CREATE SET d.name = $name, d.rows = $rows
                ON MATCH SET d.name = $name, d.rows = $rows
                """,
                source_id=source_id, name=dataset_name, rows=df_profile.get("row_count", 0)
            )
            
            # 2. Create Column Nodes
            for col in columns:
                await session.run(
                    """
                    MATCH (d:Dataset {source_id: $source_id})
                    MERGE (c:DatasetColumn {source_id: $source_id, name: $col_name})
                    ON CREATE SET c.dtype = $dtype, c.summary = $summary
                    ON MATCH SET c.dtype = $dtype, c.summary = $summary
                    MERGE (d)-[:HAS_COLUMN]->(c)
                    """,
                    source_id=source_id,
                    col_name=col["name"],
                    dtype=col.get("type", "unknown"),
                    summary=f"Min: {col.get('min', 'N/A')}, Max: {col.get('max', 'N/A')}, Sample: {col.get('sample_values', [])}"
                )
        logger.info("neo4j_csv_schema_upserted", source_id=source_id, cols=len(columns))
