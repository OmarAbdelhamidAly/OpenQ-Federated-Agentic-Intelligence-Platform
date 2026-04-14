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
        # Not in an async context, return current driver or create one (though usually called within async)
        if _driver is None:
            _driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
        return _driver

    if _driver is None or _loop != current_loop:
        # If we have an old driver from a different loop, we don't close it here 
        # to avoid blocking (it's likely tied to a dead loop from a previous task).
        # We just create a fresh one for the current task's loop.
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
        "CREATE INDEX IF NOT EXISTS FOR (f:File)      ON (f.source_id, f.path)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.source_id, d.path)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Class)     ON (c.source_id, c.file_path, c.name)",
        "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.source_id, fn.file_path, fn.name)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Table)    ON (t.source_id, t.name)",
        "CREATE INDEX IF NOT EXISTS FOR (col:Column) ON (col.source_id, col.table_name, col.name)",
        "CREATE INDEX IF NOT EXISTS FOR (ch:Chunk)   ON (ch.source_id, ch.chunk_id)",
        "CREATE INDEX IF NOT EXISTS FOR (doc:Document) ON (doc.source_id, doc.id)",
    ]
    async with driver.session() as session:
        for q in structural_indexes:
            try:
                await session.run(q)
            except Exception as exc:
                logger.warning("neo4j_index_creation_failed", query=q, error=str(exc))

        try:
            await session.run(
                """
                CREATE FULLTEXT INDEX codeEntityNames IF NOT EXISTS
                FOR (n:Class|Function|Table|Column|Chunk|File|Directory) ON EACH [n.name, n.summary, n.text]
                """
            )
        except Exception as exc:
            logger.warning("neo4j_fulltext_index_failed", error=str(exc))

        try:
            await session.run(
                """
                CREATE VECTOR INDEX codebaseSemanticIndex IF NOT EXISTS
                FOR (n:Class|Function|Chunk|Table) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 768,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
        except Exception as exc:
            logger.warning("neo4j_vector_index_failed", error=str(exc))

    logger.info("neo4j_bootstrap_complete")

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    async def close(self) -> None:
        await self.driver.close()

    async def batch_build_tree(self, source_id: str, dirs: list[dict], files: list[dict], batch_size: int = 1000) -> None:
        async with self.driver.session() as session:
            for i in range(0, len(dirs), batch_size):
                await session.run(
                    """
                    UNWIND $dirs AS d
                    MERGE (n:Directory {source_id: $source_id, path: d.path})
                    ON CREATE SET n.name = d.name
                    """,
                    source_id=source_id, dirs=dirs[i:i+batch_size],
                )
            child_dirs = [d for d in dirs if d["path"] != ""]
            if child_dirs:
                for i in range(0, len(child_dirs), batch_size):
                    await session.run(
                        """
                        UNWIND $dirs AS d
                        MATCH (parent:Directory {source_id: $source_id, path: d.parent_path})
                        MATCH (child:Directory  {source_id: $source_id, path: d.path})
                        MERGE (parent)-[:CONTAINS]->(child)
                        """,
                        source_id=source_id,
                        dirs=[{**d, "parent_path": os.path.dirname(d["path"]) or ""} for d in child_dirs][i:i+batch_size],
                    )
            if files:
                for i in range(0, len(files), batch_size):
                    await session.run(
                        """
                        UNWIND $files AS f
                        MERGE (fn:File {source_id: $source_id, path: f.path})
                        ON CREATE SET fn.name = f.name, fn.extension = f.ext
                        WITH fn, f
                        MATCH (d:Directory {source_id: $source_id, path: f.dir_path})
                        MERGE (d)-[:CONTAINS]->(fn)
                        """,
                        source_id=source_id, files=files[i:i+batch_size],
                    )

    async def batch_upsert_entities(self, source_id: str, entities: list[dict], batch_size: int = 500) -> None:
        functions = [e for e in entities if e["type"] == "Function"]
        classes   = [e for e in entities if e["type"] == "Class"]
        async with self.driver.session() as session:
            if functions:
                for i in range(0, len(functions), batch_size):
                    await session.run(
                        """
                        UNWIND $entities AS e
                        MATCH (f:File {source_id: $source_id, path: e.file_path})
                        MERGE (fn:Function {source_id: $source_id, file_path: e.file_path, name: e.name})
                        ON CREATE SET fn.chunk_id    = e.chunk_id,
                                      fn.line_start  = e.line_start,
                                      fn.line_end    = e.line_end,
                                      fn.summary     = e.summary,
                                      fn.embedding   = e.embedding
                        ON MATCH  SET fn.chunk_id    = e.chunk_id,
                                      fn.line_start  = e.line_start,
                                      fn.line_end    = e.line_end,
                                      fn.summary     = coalesce(e.summary, fn.summary),
                                      fn.embedding   = coalesce(e.embedding, fn.embedding)
                        MERGE (f)-[:DEFINES]->(fn)
                        """,
                        source_id=source_id, entities=functions[i:i+batch_size],
                    )
            if classes:
                for i in range(0, len(classes), batch_size):
                    await session.run(
                        """
                        UNWIND $entities AS e
                        MATCH (f:File {source_id: $source_id, path: e.file_path})
                        MERGE (cl:Class {source_id: $source_id, file_path: e.file_path, name: e.name})
                        ON CREATE SET cl.chunk_id    = e.chunk_id,
                                      cl.line_start  = e.line_start,
                                      cl.line_end    = e.line_end,
                                      cl.summary     = e.summary,
                                      cl.embedding   = e.embedding
                        ON MATCH  SET cl.chunk_id    = e.chunk_id,
                                      cl.line_start  = e.line_start,
                                      cl.line_end    = e.line_end,
                                      cl.summary     = coalesce(e.summary, cl.summary),
                                      cl.embedding   = coalesce(e.embedding, cl.embedding)
                        MERGE (f)-[:DEFINES]->(cl)
                        """,
                        source_id=source_id, entities=classes[i:i+batch_size],
                    )
        logger.info("neo4j_entities_upserted_async", source_id=source_id, functions=len(functions), classes=len(classes))

    async def batch_upsert_dependencies(self, source_id: str, imports: list[dict], batch_size: int = 1000) -> None:
        if not imports: return
        async with self.driver.session() as session:
            for i in range(0, len(imports), batch_size):
                await session.run(
                    """
                    UNWIND $imports AS i
                    MATCH (caller:File {source_id: $source_id, path: i.file_path})
                    MATCH (target:File {source_id: $source_id})
                    WHERE target.path ENDS WITH i.name OR target.name = i.name
                    MERGE (caller)-[:DEPENDS_ON]->(target)
                    """,
                    source_id=source_id, imports=imports[i:i+batch_size]
                )
        logger.info("neo4j_deps_upserted_async", source_id=source_id, count=len(imports))

    async def batch_upsert_calls(self, source_id: str, calls: list[dict], batch_size: int = 1000) -> None:
        if not calls: return
        async with self.driver.session() as session:
            for i in range(0, len(calls), batch_size):
                await session.run(
                    """
                    UNWIND $calls AS c
                    MATCH (caller) 
                    WHERE caller.source_id = $source_id 
                      AND caller.file_path = c.file_path
                      AND caller.name = c.caller_name
                    MATCH (target)
                    WHERE target.source_id = $source_id
                      AND target.name = c.name
                      AND (target:Function OR target:Class)
                    MERGE (caller)-[:CALLS]->(target)
                    """,
                    source_id=source_id, calls=calls[i:i+batch_size]
                )
        logger.info("neo4j_calls_upserted_async", source_id=source_id, count=len(calls))

    async def execute_cypher(self, query: str, params: dict) -> list[dict]:
        async with self.driver.session() as session:
            records = await session.run(query, **params)
            return [rec.data() async for rec in records]

    async def get_schema_stats(self, source_id: str) -> dict:
        async with self.driver.session() as session:
            records = await session.run(
                "MATCH (n) WHERE n.source_id = $source_id RETURN labels(n)[0] AS label, count(n) AS cnt",
                source_id=source_id,
            )
            rows = [r.data() async for r in records]
        return {row["label"]: row["cnt"] for row in rows if row["label"]}

    async def delete_source_graph(self, source_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(
                "CALL { MATCH (n {source_id: $source_id}) DETACH DELETE n } IN TRANSACTIONS OF 500 ROWS",
                source_id=source_id,
            )
        logger.info("neo4j_source_deleted_async", source_id=source_id)
        
    async def batch_upsert_document_structure(self, source_id: str, document_id: str, chunks: list[dict], batch_size: int = 500) -> None:
        async with self.driver.session() as session:
            await session.run(
                "MERGE (d:Document {source_id: $source_id, id: $document_id})",
                source_id=source_id, document_id=document_id
            )
            for i in range(0, len(chunks), batch_size):
                await session.run(
                    """
                    UNWIND $chunks AS ch
                    MERGE (chunk:Chunk {source_id: $source_id, chunk_id: ch.chunk_id})
                    ON CREATE SET chunk.text      = ch.text,
                                  chunk.page      = ch.page,
                                  chunk.embedding = ch.embedding
                    ON MATCH SET  chunk.text      = ch.text,
                                  chunk.embedding = coalesce(ch.embedding, chunk.embedding)
                    WITH chunk
                    MATCH (d:Document {source_id: $source_id, id: $document_id})
                    MERGE (d)-[:HAS_CHUNK]->(chunk)
                    """,
                    source_id=source_id, document_id=document_id, chunks=chunks[i:i+batch_size]
                )
        logger.info("neo4j_document_structure_upserted_async", source_id=source_id, chunks=len(chunks))

    async def batch_upsert_data_schema(self, source_id: str, tables: list[dict]) -> None:
        async with self.driver.session() as session:
            for table in tables:
                table_name = table["name"]
                await session.run(
                    "MERGE (t:Table {source_id: $source_id, name: $table_name})",
                    source_id=source_id, table_name=table_name
                )
                if "columns" in table:
                    await session.run(
                        """
                        UNWIND $columns AS col
                        MATCH (t:Table {source_id: $source_id, name: $table_name})
                        MERGE (c:Column {source_id: $source_id, table_name: $table_name, name: col.name})
                        ON CREATE SET c.dtype = col.dtype,
                                      c.summary = col.summary
                        MERGE (t)-[:HAS_COLUMN]->(c)
                        """,
                        source_id=source_id, table_name=table_name, columns=table["columns"]
                    )
        logger.info("neo4j_data_schema_upserted_async", source_id=source_id, tables=len(tables))

    async def execute_nexus_bridge(self, source_id: str) -> None:
        async with self.driver.session() as session:
            # 1. Advanced Vector Similarity Mapping (Score > 0.85)
            await session.run(
                """
                MATCH (t:Table {source_id: $source_id})
                WHERE t.embedding IS NOT NULL
                CALL db.index.vector.queryNodes("codebaseSemanticIndex", 3, t.embedding) YIELD node AS c, score
                WHERE score > 0.85 AND c:Class AND c.source_id = $source_id
                MERGE (c)-[:REPRESENTS_DATA]->(t)
                """,
                source_id=source_id
            )

            # 2. String matching as fallback
            await session.run(
                """
                MATCH (c:Class {source_id: $source_id}), (t:Table {source_id: $source_id})
                WHERE (toLower(c.name) = toLower(t.name) 
                   OR toLower(c.name) CONTAINS toLower(t.name)
                   OR toLower(t.name) CONTAINS toLower(c.name))
                  AND NOT exists((c)-[:REPRESENTS_DATA]->(t))
                MERGE (c)-[:REPRESENTS_DATA]->(t)
                """,
                source_id=source_id
            )
            
            # 3. PDF Mentions mapping
            await session.run(
                """
                MATCH (ch:Chunk {source_id: $source_id}), (entity)
                WHERE entity.source_id = $source_id 
                  AND (entity:Class OR entity:Function OR entity:Table)
                  AND ch.text CONTAINS entity.name
                MERGE (ch)-[:MENTIONS]->(entity)
                """,
                source_id=source_id
            )
        logger.info("neo4j_nexus_bridge_executed_async", source_id=source_id)

    async def batch_upsert_directory_metadata(self, source_id: str, dirs: list[dict], batch_size: int = 500) -> None:
        async with self.driver.session() as session:
            for i in range(0, len(dirs), batch_size):
                await session.run(
                    """
                    UNWIND $dirs AS d
                    MATCH (n:Directory {source_id: $source_id, path: d.path})
                    SET n.summary = d.summary,
                        n.domain = coalesce(d.domain, 'General'),
                        n.updated_at = timestamp()
                    """,
                    source_id=source_id, dirs=dirs[i:i+batch_size],
                )
        logger.info("neo4j_directory_metadata_upserted", source_id=source_id, count=len(dirs))

    async def batch_upsert_file_metadata(self, source_id: str, files: list[dict], batch_size: int = 500) -> None:
        async with self.driver.session() as session:
            for i in range(0, len(files), batch_size):
                await session.run(
                    """
                    UNWIND $files AS f
                    MATCH (n:File {source_id: $source_id, path: f.path})
                    SET n.summary = f.summary,
                        n.updated_at = timestamp()
                    """,
                    source_id=source_id, files=files[i:i+batch_size],
                )
        logger.info("neo4j_file_metadata_upserted", source_id=source_id, count=len(files))

    async def get_graph_data(self, source_id: str) -> dict:
        async with self.driver.session() as session:
            nodes_query = """
            MATCH (n)
            WHERE n.source_id = $source_id
            RETURN id(n) AS id, labels(n)[0] AS type, n.name AS name, n.path AS path, n.summary AS summary
            """
            nodes_records = await session.run(nodes_query, source_id=source_id)
            nodes_result = [r.data() async for r in nodes_records]
            
            links_query = """
            MATCH (s)-[r]->(t)
            WHERE s.source_id = $source_id AND t.source_id = $source_id
            RETURN id(s) AS source, id(t) AS target, type(r) AS type
            """
            links_records = await session.run(links_query, source_id=source_id)
            links_result = [r.data() async for r in links_records]
            
            return {
                "nodes": nodes_result,
                "links": links_result
            }
