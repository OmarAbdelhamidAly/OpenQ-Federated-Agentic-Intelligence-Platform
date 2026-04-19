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
    """Create structural, full-text and vector indexes."""
    driver = _get_driver()
    structural_indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (ch:Chunk)   ON (ch.source_id, ch.chunk_id)",
        "CREATE INDEX IF NOT EXISTS FOR (doc:Document) ON (doc.source_id, doc.id)",
        "CREATE INDEX IF NOT EXISTS FOR (s:Section)  ON (s.source_id, s.id)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Entity)   ON (e.source_id, e.name)",
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

    async def run_query(self, query: str, parameters: dict[str, Any] = None) -> Any:
        """Run a raw Cypher query asynchronously."""
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            return await result.data()

    async def batch_upsert_document_structure(
        self, 
        source_id: str, 
        document_id: str, 
        chunks: list[dict], 
        taxonomy: dict = None
    ) -> None:
        """Sync basic page-based document structure to Neo4j."""
        taxonomy = taxonomy or {}
        async with self.driver.session() as session:
            # 1. Upsert Document with Taxonomy properties
            await session.run(
                """
                MERGE (d:Document {source_id: $source_id, id: $document_id})
                SET d.industry = $industry,
                    d.doc_type = $doc_type,
                    d.updated_at = timestamp()
                """,
                source_id=source_id,
                document_id=document_id,
                industry=taxonomy.get("industry", "Unknown"),
                doc_type=taxonomy.get("doc_type", "Unclassified")
            )
            
            # 2. Upsert Chunks
            await session.run(
                """
                UNWIND $chunks AS ch
                MERGE (chunk:Chunk {source_id: $source_id, chunk_id: ch.chunk_id})
                ON CREATE SET chunk.text       = ch.text,
                              chunk.page       = ch.page,
                              chunk.chunk_index = ch.chunk_index
                WITH chunk
                MATCH (d:Document {source_id: $source_id, id: $document_id})
                MERGE (d)-[:HAS_CHUNK]->(chunk)
                """,
                source_id=source_id,
                document_id=document_id,
                chunks=chunks
            )
        logger.info("neo4j_doc_sync_done_async", source_id=source_id, chunks=len(chunks))

    async def batch_upsert_strategic_hierarchy(self, source_id: str, document_id: str, sections: list[dict]) -> None:
        """Sync Chapter/Section hierarchy for Strategic Nexus ingestion."""
        async with self.driver.session() as session:
            for sec in sections:
                # 1. Create Section
                await session.run(
                    """
                    MERGE (s:Section {source_id: $source_id, id: $sec_id})
                    ON CREATE SET s.title   = $title,
                                  s.summary = $summary,
                                  s.level   = $level
                    WITH s
                    MATCH (d:Document {source_id: $source_id, id: $document_id})
                    MERGE (d)-[:HAS_SECTION]->(s)
                    """,
                    source_id=source_id,
                    document_id=document_id,
                    sec_id=sec["id"],
                    title=sec["title"],
                    summary=sec.get("summary", ""),
                    level=sec.get("level", 1)
                )
                
                # 2. Link Section to its Chunks
                if "chunk_ids" in sec:
                    await session.run(
                        """
                        UNWIND $chunk_ids AS cid
                        MATCH (s:Section {source_id: $source_id, id: $sec_id})
                        MATCH (c:Chunk {source_id: $source_id, chunk_id: cid})
                        MERGE (s)-[:HAS_CHUNK]->(c)
                        """,
                        source_id=source_id,
                        sec_id=sec["id"],
                        chunk_ids=sec["chunk_ids"]
                    )
        logger.info("neo4j_strategic_hierarchy_sync_done", source_id=source_id, sections=len(sections))

    async def batch_upsert_entities(self, source_id: str, entities: list[dict]) -> None:
        """Link Chunks to Domain Entities (Concepts, Terms)."""
        async with self.driver.session() as session:
            for ent in entities:
                await session.run(
                    """
                    MERGE (e:Entity {source_id: $source_id, name: $name})
                    ON CREATE SET e.type        = $type,
                                  e.description = $desc
                    WITH e
                    UNWIND $chunk_ids AS cid
                    MATCH (c:Chunk {source_id: $source_id, chunk_id: cid})
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    source_id=source_id,
                    name=ent["name"],
                    type=ent.get("type", "Concept"),
                    desc=ent.get("description", ""),
                    chunk_ids=ent["chunk_ids"]
                )
        logger.info("neo4j_entities_sync_done", source_id=source_id, count=len(entities))
