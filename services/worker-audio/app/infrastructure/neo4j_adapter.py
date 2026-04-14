import os
import structlog
from neo4j import GraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        logger.info("neo4j_driver_created")
    return _driver

def bootstrap_neo4j() -> None:
    """Create structural, full-text and vector indexes."""
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
        "CREATE INDEX IF NOT EXISTS FOR (m:Media)     ON (m.source_id, m.id)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Entity)    ON (e.source_id, e.name)",
    ]
    with driver.session() as session:
        for q in structural_indexes:
            try:
                session.run(q)
            except Exception as exc:
                logger.warning("neo4j_index_creation_failed", query=q, error=str(exc))

        try:
            session.run(
                """
                CREATE FULLTEXT INDEX codeEntityNames IF NOT EXISTS
                FOR (n:Class|Function|Table|Column|Chunk|Media|Entity) ON EACH [n.name, n.summary, n.text]
                """
            )
        except Exception as exc:
            logger.warning("neo4j_fulltext_index_failed", error=str(exc))

    logger.info("neo4j_bootstrap_complete")

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    def close(self) -> None:
        pass

    def batch_upsert_document_structure(self, source_id: str, document_id: str, chunks: list[dict]) -> None:
        """Lexical Layer: Sync chunks and document metadata to Neo4j."""
        with self.driver.session() as session:
            session.run(
                "MERGE (d:Document {source_id: $source_id, id: $document_id})",
                source_id=source_id, document_id=document_id
            )
            session.run(
                """
                UNWIND $chunks AS ch
                MERGE (chunk:Chunk {source_id: $source_id, chunk_id: ch.chunk_id})
                ON CREATE SET chunk.text      = ch.text,
                              chunk.page      = ch.get('page'),
                              chunk.embedding = ch.get('embedding')
                ON MATCH SET  chunk.text      = ch.text,
                              chunk.embedding = ch.get('embedding', chunk.embedding)
                WITH chunk
                MATCH (d:Document {source_id: $source_id, id: $document_id})
                MERGE (d)-[:HAS_CHUNK]->(chunk)
                """,
                source_id=source_id, document_id=document_id, chunks=chunks
            )
        logger.info("neo4j_document_structure_upserted", source_id=source_id, chunks=len(chunks))

    def batch_upsert_data_schema(self, source_id: str, tables: list[dict]) -> None:
        """Domain Layer: Sync SQL/CSV/JSON schema to Neo4j."""
        with self.driver.session() as session:
            for table in tables:
                table_name = table["name"]
                session.run(
                    "MERGE (t:Table {source_id: $source_id, name: $table_name})",
                    source_id=source_id, table_name=table_name
                )
                if "columns" in table:
                    session.run(
                        """
                        UNWIND $columns AS col
                        MATCH (t:Table {source_id: $source_id, name: $table_name})
                        MERGE (c:Column {source_id: $source_id, table_name: $table_name, name: col.name})
                        ON CREATE SET c.dtype = col.get('dtype'),
                                      c.summary = col.get('summary')
                        MERGE (t)-[:HAS_COLUMN]->(c)
                        """,
                        source_id=source_id, table_name=table_name, columns=table["columns"]
                    )
        logger.info("neo4j_data_schema_upserted", source_id=source_id, tables=len(tables))

    def batch_upsert_multimodal_entities(self, source_id: str, media_id: str, media_type: str, entities: list[dict]) -> None:
        """Visual/Auditory Layer: Sync objects, speakers, and scenes to Neo4j."""
        with self.driver.session() as session:
            session.run(
                "MERGE (m:Media {source_id: $source_id, id: $media_id}) ON CREATE SET m.type = $media_type",
                source_id=source_id, media_id=media_id, media_type=media_type
            )
            session.run(
                """
                UNWIND $entities AS e
                MERGE (ent:Entity {source_id: $source_id, name: e.name})
                ON CREATE SET ent.type = e.get('type'),
                              ent.summary = e.get('summary')
                WITH ent
                MATCH (m:Media {source_id: $source_id, id: $media_id})
                MERGE (m)-[:CONTAINS]->(ent)
                """,
                source_id=source_id, media_id=media_id, entities=entities
            )
        logger.info("neo4j_multimodal_entities_upserted", source_id=source_id, entities=len(entities))

    def execute_nexus_bridge(self, source_id: str) -> None:
        """Subject Layer: The Discovery Engine — Auto-stitch pillars."""
        with self.driver.session() as session:
            # 1. Map Code Classes to SQL Tables by name similarity
            session.run(
                """
                MATCH (c:Class {source_id: $source_id}), (t:Table {source_id: $source_id})
                WHERE toLower(c.name) = toLower(t.name) 
                   OR toLower(c.name) CONTAINS toLower(t.name)
                   OR toLower(t.name) CONTAINS toLower(c.name)
                MERGE (c)-[:REPRESENTS_DATA]->(t)
                """
            )
            
            # 2. Map PDF Chunks to Code/Data entities
            session.run(
                """
                MATCH (ch:Chunk {source_id: $source_id}), (entity)
                WHERE entity.source_id = $source_id 
                  AND (entity:Class OR entity:Function OR entity:Table)
                  AND ch.text CONTAINS entity.name
                MERGE (ch)-[:MENTIONS]->(entity)
                """
            )
        logger.info("neo4j_nexus_bridge_executed", source_id=source_id)

    def nexus_global_search(self, question: str, source_ids: list[str]) -> list[dict]:
        """Discovery Layer: Find relevant nodes across selected pillars using Cypher."""
        with self.driver.session() as session:
            query = """
            CALL db.index.fulltext.queryNodes("codeEntityNames", $question) YIELD node, score
            WHERE node.source_id IN $source_ids
            RETURN labels(node)[0] AS type, node.name AS name, node.source_id AS source_id, score
            ORDER BY score DESC LIMIT 10
            """
            return session.run(query, question=question, source_ids=source_ids).data()

    def get_graph_data(self, source_id: str) -> dict:
        """Fetch all nodes and relationships for a specific source to build a visual graph."""
        with self.driver.session() as session:
            nodes_query = """
            MATCH (n) WHERE n.source_id = $source_id
            RETURN id(n) AS id, labels(n)[0] AS type, n.name AS name, n.path AS path, n.summary AS summary
            """
            nodes_result = session.run(nodes_query, source_id=source_id).data()
            
            links_query = """
            MATCH (s)-[r]->(t)
            WHERE s.source_id = $source_id AND t.source_id = $source_id
            RETURN id(s) AS source, id(t) AS target, type(r) AS type
            """
            links_result = session.run(links_query, source_id=source_id).data()
            
            return {"nodes": nodes_result, "links": links_result}
