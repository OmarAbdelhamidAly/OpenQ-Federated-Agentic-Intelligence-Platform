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
        "CREATE INDEX IF NOT EXISTS FOR (r:JSONRoot) ON (r.source_id)",
        "CREATE INDEX IF NOT EXISTS FOR (o:JSONObject) ON (o.source_id, o.path)",
        "CREATE INDEX IF NOT EXISTS FOR (f:JSONField) ON (f.source_id, f.path)",
    ]
    async with driver.session() as session:
        for q in indexes:
            try:
                await session.run(q)
            except Exception as exc:
                logger.warning("json_neo4j_index_failed", query=q, error=str(exc))
    logger.info("json_neo4j_bootstrap_complete")

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    async def close(self) -> None:
        await self.driver.close()

    async def upsert_json_schema(self, source_id: str, schema: dict) -> None:
        """
        Recursively extract field metadata from actual parsed JSON object up to depth=4 
        or use the precomputed schema_json if provided.
        """
        async with self.driver.session() as session:
            # 1. Root
            await session.run(
                """
                MERGE (r:JSONRoot {source_id: $source_id})
                ON CREATE SET r.type = $type, r.item_count = $count
                ON MATCH SET r.type = $type, r.item_count = $count
                """,
                source_id=source_id, 
                type=schema.get("source_type", "unknown"),
                count=schema.get("item_count", schema.get("field_count", 1))
            )
            
            # Simple 1-level indexing assuming standard "fields" list from profiler.
            fields = schema.get("fields", [])
            for field in fields:
                await session.run(
                    """
                    MATCH (r:JSONRoot {source_id: $source_id})
                    MERGE (f:JSONField {source_id: $source_id, name: $field_name})
                    MERGE (r)-[:HAS_FIELD]->(f)
                    """,
                    source_id=source_id, field_name=str(field)
                )
        logger.info("neo4j_json_schema_upserted", source_id=source_id, fields=len(schema.get("fields", [])))
