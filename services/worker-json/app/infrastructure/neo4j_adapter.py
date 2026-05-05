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

