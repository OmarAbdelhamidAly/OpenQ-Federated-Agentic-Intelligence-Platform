import os
import structlog
from neo4j import AsyncGraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

import asyncio

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
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
        return _driver

    if _driver is None or _loop != current_loop:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        _loop = current_loop
        logger.info("neo4j_driver_reinitialized_for_new_loop", loop_id=id(current_loop))
    return _driver

async def bootstrap_neo4j() -> None:
    """Create structural, full-text and vector indexes for the Nexus Orchestrator."""
    driver = _get_driver()
    structural_indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (f:File)      ON (f.source_id, f.path)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.source_id, d.path)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Class)     ON (c.source_id, c.file_path, c.name)",
        "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.source_id, fn.file_path, fn.name)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Table)    ON (t.source_id, t.name)",
        "CREATE INDEX IF NOT EXISTS FOR (col:Column) ON (col.source_id, col.table_name, col.name)",
        "CREATE INDEX IF NOT EXISTS FOR (ch:Chunk)   ON (ch.source_id, ch.chunk_id)",
        "CREATE INDEX IF NOT EXISTS FOR (doc:Document) ON (doc.source_id, doc.id)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Entity)    ON (e.source_id, e.name)",
        "CREATE INDEX IF NOT EXISTS FOR (s:Section)   ON (s.source_id, s.title)",
    ]
    async with driver.session() as session:
        for q in structural_indexes:
            try:
                await session.run(q)
            except Exception as exc:
                logger.warning("neo4j_index_creation_failed", query=q, error=str(exc))

        try:
            # Expanded Full-text Search to include Tiered Code components and PDF Sections/Entities
            await session.run(
                """
                CREATE FULLTEXT INDEX codeEntityNames IF NOT EXISTS
                FOR (n:Class|Function|Table|Column|Chunk|Entity|Section|File|Directory) 
                ON EACH [n.name, n.title, n.summary, n.text, n.description]
                """
            )
        except Exception as exc:
            logger.warning("neo4j_fulltext_index_failed", error=str(exc))

    logger.info("neo4j_nexus_alignment_complete")

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    async def close(self) -> None:
        await self.driver.close()


    async def nexus_global_search(self, question: str, source_ids: list[str]) -> list[dict]:
        """Discovery Layer: Strategic Search across tiered components."""
        # Sanitize for Lucene (Special chars: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /)
        import re
        clean_query = re.sub(r'[^\w\s]', ' ', question).strip()
        if not clean_query:
            clean_query = "*"
            
        async with self.driver.session() as session:
            query = """
            CALL db.index.fulltext.queryNodes("codeEntityNames", $question) YIELD node, score
            WHERE node.source_id IN $source_ids
            RETURN labels(node)[0] AS type, 
                   COALESCE(node.name, node.title, "Unnamed") AS name, 
                   node.source_id AS source_id, 
                   score,
                   node.summary AS summary
            ORDER BY score DESC LIMIT 10
            """
            result = await session.run(query, question=clean_query, source_ids=source_ids)
            return [rec.data() async for rec in result]

    async def execute_cypher(self, query: str, params: dict) -> list[dict]:
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            return [rec.data() async for rec in result]

    async def fetch_multi_source_context(self, source_ids: list[str]) -> dict:
        """Fetch all entities and cross-pillar relationships for multiple source_ids.
        
        Supports 5 pillars: Code (Class/Function/File), SQL (Table/Column),
        PDF (Chunk/Entity/Section), CSV (Dataset/DatasetColumn), JSON (JSONRoot/JSONField).
        """
        async with self.driver.session() as session:
            # 1. Core nodes — Code, SQL, PDF pillars
            entities_res = await session.run(
                """
                MATCH (n)
                WHERE n.source_id IN $source_ids
                  AND (n:Class OR n:Function OR n:Table OR n:Column
                       OR n:Chunk OR n:Entity OR n:File OR n:Section)
                RETURN n.source_id AS sid,
                       labels(n)[0]  AS type,
                       COALESCE(n.name, n.title, n.path, 'Unnamed') AS name,
                       COALESCE(n.summary, n.text, n.description, '') AS summary,
                       COALESCE(n.archetype, '') AS archetype
                ORDER BY type, name
                LIMIT 120
                """,
                source_ids=source_ids
            )
            entities = [r.data() async for r in entities_res]

            # 2. CSV pillar — Dataset schema & columns
            csv_res = await session.run(
                """
                MATCH (d:Dataset)-[:HAS_COLUMN]->(c:DatasetColumn)
                WHERE d.source_id IN $source_ids
                RETURN d.source_id AS sid,
                       'DatasetColumn' AS type,
                       c.name AS name,
                       COALESCE(c.summary, '') AS summary,
                       d.name AS archetype
                LIMIT 60
                """,
                source_ids=source_ids
            )
            csv_nodes = [r.data() async for r in csv_res]

            # 3. JSON pillar — Root and fields
            json_res = await session.run(
                """
                MATCH (r:JSONRoot)-[:HAS_FIELD]->(f:JSONField)
                WHERE r.source_id IN $source_ids
                RETURN r.source_id AS sid,
                       'JSONField' AS type,
                       f.name AS name,
                       '' AS summary,
                       '' AS archetype
                LIMIT 60
                """,
                source_ids=source_ids
            )
            json_nodes = [r.data() async for r in json_res]

            all_entities = entities + csv_nodes + json_nodes

            # 4. Cross-pillar relationships (different source_ids)
            cross_res = await session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE a.source_id IN $source_ids
                  AND b.source_id IN $source_ids
                  AND a.source_id <> b.source_id
                RETURN labels(a)[0]                          AS from_type,
                       COALESCE(a.name, 'Unnamed')           AS from_name,
                       type(r)                               AS relationship,
                       labels(b)[0]                          AS to_type,
                       COALESCE(b.name, 'Unnamed')           AS to_name
                LIMIT 100
                """,
                source_ids=source_ids
            )
            cross_links = [r.data() async for r in cross_res]

            # 5. Intra-source relationships for local context
            intra_res = await session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE a.source_id IN $source_ids
                  AND b.source_id IN $source_ids
                  AND a.source_id = b.source_id
                RETURN labels(a)[0]                          AS from_type,
                       COALESCE(a.name, 'Unnamed')           AS from_name,
                       type(r)                               AS relationship,
                       labels(b)[0]                          AS to_type,
                       COALESCE(b.name, 'Unnamed')           AS to_name
                LIMIT 80
                """,
                source_ids=source_ids
            )
            intra_links = [r.data() async for r in intra_res]

        logger.info("neo4j_multi_source_context_fetched",
                    entities=len(all_entities),
                    csv_cols=len(csv_nodes),
                    json_fields=len(json_nodes),
                    cross_links=len(cross_links),
                    intra_links=len(intra_links))
        return {
            "entities": all_entities,
            "cross_pillar_links": cross_links,
            "intra_links": intra_links,
        }


