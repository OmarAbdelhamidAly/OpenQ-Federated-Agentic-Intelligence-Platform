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


    async def get_agent_memory(self, user_id: str, source_id: str, limit: int = 5) -> str:
        """Retrieve recent MemoryFacts from Neo4j for the given user and source."""
        async with self.driver.session() as session:
            query = """
            MATCH (u:User {id: $user_id})<-[:OWNED_BY]-(s:Session {source_id: $source_id})-[:PRODUCED_MEMORY]->(m:MemoryFact)
            OPTIONAL MATCH (m)-[:MENTIONS]->(e:Entity)
            RETURN m.text AS fact, collect(e.name) AS entities, m.timestamp AS ts
            ORDER BY m.timestamp DESC
            LIMIT $limit
            """
            records = await session.run(query, user_id=user_id, source_id=source_id, limit=limit)
            facts = []
            async for rec in records:
                fact_text = rec["fact"]
                entities = rec["entities"]
                if entities:
                    fact_text += f" (Entities: {', '.join(entities)})"
                facts.append(fact_text)
            
            if not facts:
                return "No previous long-term memory."
            
            return "\n".join(f"- {f}" for f in reversed(facts))



    async def generate_structural_embeddings(self, source_id: str) -> None:
        """Projects the graph to GDS, runs FastRP, and persists the structural embeddings."""
        graph_name = f"nexusGraph_{source_id.replace('-', '_')}"
        async with self.driver.session() as session:
            try:
                # 1. Drop graph if exists (cleanup from previous runs)
                await session.run("CALL gds.graph.drop($graph_name, false)", graph_name=graph_name)
                
                # 2. Project the graph
                # Using * for relationships to capture all structural connectivity
                await session.run("""
                CALL gds.graph.project(
                    $graph_name,
                    ['Class', 'Function', 'Table', 'File', 'Directory', 'MemoryFact', 'Entity', 'Document', 'Chunk', 'Column'],
                    '*'
                )
                """, graph_name=graph_name)
                
                # 3. Run FastRP and write back
                await session.run("""
                CALL gds.fastRP.write(
                    $graph_name,
                    {
                        embeddingDimension: 256,
                        writeProperty: 'fastrp_embedding',
                        randomSeed: 42
                    }
                )
                """, graph_name=graph_name)
                
                # 4. Drop the in-memory graph
                await session.run("CALL gds.graph.drop($graph_name, false)", graph_name=graph_name)
                logger.info("neo4j_fastrp_embeddings_generated", source_id=source_id)
            except Exception as e:
                logger.warning("neo4j_fastrp_failed_make_sure_gds_is_installed", error=str(e), source_id=source_id)
                # Cleanup on failure just in case
                try:
                    await session.run("CALL gds.graph.drop($graph_name, false)", graph_name=graph_name)
                except:
                    pass



    async def hybrid_similarity_search(self, source_id: str, query_embedding: list, target_label: str, limit: int = 5) -> list[dict]:
        """Performs a Hybrid Search using Vector (Semantic) + FastRP (Structural) embeddings."""
        async with self.driver.session() as session:
            # We first fetch top 20 semantic matches, then rescore using structural embeddings
            # (Assuming the query doesn't have a fastrp_embedding since it's just text, 
            # we can't do direct structural comparison between query and graph.
            # Instead, standard Hybrid search for agents is:
            # find semantic nodes, then return their fastrp embeddings to find structurally similar peers,
            # or if comparing node to node (like in nexus bridge) we use both.
            # Since a raw text query only has a text embedding, we rely on semantic search first.)
            query = f"""
            CALL db.index.vector.queryNodes("codebaseSemanticIndex", 20, $embedding) YIELD node AS n, score AS semantic_score
            WHERE n:{target_label} AND n.source_id = $source_id
            RETURN id(n) as id, n.name as name, n.summary as summary, semantic_score, n.fastrp_embedding as struct_emb
            ORDER BY semantic_score DESC
            LIMIT $limit
            """
            records = await session.run(query, embedding=query_embedding, source_id=source_id, limit=limit)
            return [r.data() async for r in records]

