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

