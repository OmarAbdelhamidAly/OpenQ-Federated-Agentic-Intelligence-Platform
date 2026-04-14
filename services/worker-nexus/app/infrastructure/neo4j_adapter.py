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

    async def execute_nexus_bridge(self, source_id: str) -> None:
        """Subject Layer: The Strategic Stitching Engine — Multi-pillar correlation logic."""
        async with self.driver.session() as session:
            # 1. Map Code Classes to SQL Tables (Architectural Match)
            await session.run(
                """
                MATCH (c:Class {source_id: $source_id}), (t:Table {source_id: $source_id})
                WHERE toLower(c.name) = toLower(t.name) 
                   OR toLower(c.name) CONTAINS toLower(t.name)
                   OR toLower(t.name) CONTAINS toLower(c.name)
                MERGE (c)-[:REPRESENTS_DATA]->(t)
                """,
                source_id=source_id
            )
            
            # 2. Map PDF Entities to Database/Code (Semantic Match)
            await session.run(
                """
                MATCH (e:Entity {source_id: $source_id}), (target)
                WHERE target.source_id = $source_id 
                  AND (target:Class OR target:Function OR target:Table OR target:Column)
                  AND (toLower(e.name) = toLower(target.name) OR toLower(target.name) CONTAINS toLower(e.name))
                MERGE (e)-[:REFERS_TO]->(target)
                """,
                source_id=source_id
            )

            # 3. Linked Chunks to Entities
            await session.run(
                """
                MATCH (ch:Chunk {source_id: $source_id}), (entity)
                WHERE entity.source_id = $source_id 
                  AND (entity:Class OR entity:Function OR entity:Table OR entity:Column OR entity:Entity)
                  AND ch.text CONTAINS entity.name
                MERGE (ch)-[:MENTIONS]->(entity)
                """,
                source_id=source_id
            )
            
        logger.info("neo4j_strategic_bridge_executed_async", source_id=source_id)

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

    async def forge_cross_source_links(self, source_ids: list[str]) -> dict:
        """Dynamically create cross-pillar relationships between all provided source_ids.
        
        5-pillar cross-linking:
          1. Code Class  ↔ SQL Table
          2. PDF Entity  ↔ Code/SQL nodes
          3. PDF Chunk   ↔ any named entity (mentions)
          4. CSV Column  ↔ SQL Column  (structural twin)
          5. JSON Field  ↔ Code Class/Function (config mapping)
        """
        async with self.driver.session() as session:

            # ── Link 1: Code Class ↔ SQL Table ────────────────────────────────
            r1 = await session.run(
                """
                MATCH (c:Class), (t:Table)
                WHERE c.source_id IN $source_ids AND t.source_id IN $source_ids
                  AND c.source_id <> t.source_id
                  AND (toLower(c.name) = toLower(t.name)
                    OR toLower(c.name) CONTAINS toLower(t.name)
                    OR toLower(t.name) CONTAINS toLower(c.name))
                MERGE (c)-[:REPRESENTS_DATA]->(t)
                RETURN count(*) AS created
                """,
                source_ids=source_ids
            )
            r1d = await r1.single()

            # ── Link 2: PDF Entity ↔ Code/SQL nodes ───────────────────────────
            r2 = await session.run(
                """
                MATCH (e:Entity), (target)
                WHERE e.source_id IN $source_ids AND target.source_id IN $source_ids
                  AND e.source_id <> target.source_id
                  AND (target:Class OR target:Function OR target:Table OR target:Column)
                  AND (toLower(e.name) = toLower(target.name)
                    OR toLower(target.name) CONTAINS toLower(e.name))
                MERGE (e)-[:REFERS_TO]->(target)
                RETURN count(*) AS created
                """,
                source_ids=source_ids
            )
            r2d = await r2.single()

            # ── Link 3: PDF Chunks ↔ any named entity (mentions) ──────────────
            r3 = await session.run(
                """
                MATCH (ch:Chunk), (entity)
                WHERE ch.source_id IN $source_ids AND entity.source_id IN $source_ids
                  AND ch.source_id <> entity.source_id
                  AND (entity:Class OR entity:Function OR entity:Table
                       OR entity:Column OR entity:Entity
                       OR entity:DatasetColumn OR entity:JSONField)
                  AND ch.text CONTAINS entity.name
                MERGE (ch)-[:MENTIONS]->(entity)
                RETURN count(*) AS created
                """,
                source_ids=source_ids
            )
            r3d = await r3.single()

            # ── Link 4: CSV DatasetColumn ↔ SQL Column (structural twin) ──────
            r4 = await session.run(
                """
                MATCH (dc:DatasetColumn), (sc:Column)
                WHERE dc.source_id IN $source_ids AND sc.source_id IN $source_ids
                  AND dc.source_id <> sc.source_id
                  AND (toLower(dc.name) = toLower(sc.name)
                    OR toLower(dc.name) CONTAINS toLower(sc.name)
                    OR toLower(sc.name) CONTAINS toLower(dc.name))
                MERGE (dc)-[:STRUCTURALLY_MAPS_TO]->(sc)
                RETURN count(*) AS created
                """,
                source_ids=source_ids
            )
            r4d = await r4.single()

            # ── Link 5: JSON Field ↔ Code Class/Function (config mapping) ─────
            r5 = await session.run(
                """
                MATCH (jf:JSONField), (target)
                WHERE jf.source_id IN $source_ids AND target.source_id IN $source_ids
                  AND jf.source_id <> target.source_id
                  AND (target:Class OR target:Function)
                  AND (toLower(jf.name) = toLower(target.name)
                    OR toLower(target.name) CONTAINS toLower(jf.name)
                    OR toLower(jf.name) CONTAINS toLower(target.name))
                MERGE (jf)-[:CONFIGURES]->(target)
                RETURN count(*) AS created
                """,
                source_ids=source_ids
            )
            r5d = await r5.single()

        counts = {
            "class_table":      r1d["created"] if r1d else 0,
            "entity_target":    r2d["created"] if r2d else 0,
            "chunk_mention":    r3d["created"] if r3d else 0,
            "csv_sql_column":   r4d["created"] if r4d else 0,
            "json_code_field":  r5d["created"] if r5d else 0,
        }
        logger.info("neo4j_cross_source_links_forged", **counts)
        return counts
