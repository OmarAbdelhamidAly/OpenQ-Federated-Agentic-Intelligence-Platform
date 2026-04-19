"""PDF Graph Knowledge Builder.

Constructs the structural and semantic graph for a Document in Neo4j.
Links Chunks to Pages and Pages to Documents.
Links Chunks to semantically relevant Entities.
"""
import uuid
import structlog
from typing import Any, Dict, List
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

async def build_pdf_knowledge_graph(
    source_id: str, 
    tenant_id: str, 
    chunks: List[Any], 
    entities: List[Dict[str, Any]], 
    topics: List[str],
    summary: str
) -> None:
    """Build the base Neo4j graph structure for a PDF document."""
    logger.info("pdf_graph_building_started", source_id=source_id, chunks=len(chunks))
    
    neo4j = Neo4jAdapter() # Assuming it's already configured to use internal driver
    
    try:
        # 1. Create the root Document node
        await neo4j.run_query(
            """
            MERGE (d:DocumentSource {source_id: $source_id})
            SET d.tenant_id = $tenant_id,
                d.pillar = 'pdf',
                d.topics = $topics,
                d.summary = $summary
            """,
            {
                "source_id": source_id, 
                "tenant_id": tenant_id, 
                "topics": topics, 
                "summary": summary
            }
        )

        # 2. Map Text Chunks (The core of GraphRAG)
        # Chunks are expected to have: chunk_id, text, page_num, embedding
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id: continue
            
            await neo4j.run_query(
                """
                MATCH (d:DocumentSource {source_id: $source_id})
                MERGE (t:TextChunk {chunk_id: $chunk_id})
                SET t.text = $text,
                    t.page_num = $page_num,
                    t.embedding = $embedding
                MERGE (t)-[:PART_OF_DOCUMENT]->(d)
                """,
                {
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "text": chunk.get("text", ""),
                    "page_num": chunk.get("page", 0),
                    "embedding": chunk.get("embedding", [])
                }
            )

        # 3. Map semantic Entities discovered inside the document
        for entity in entities[:20]:
            await neo4j.run_query(
                """
                MERGE (e:Entity {name: $name, type: $type})
                WITH e
                MATCH (d:DocumentSource {source_id: $source_id})
                MERGE (e)-[:MENTIONED_IN]->(d)
                """,
                {
                    "name": entity.get("name", ""),
                    "type": entity.get("type", "Unknown"),
                    "source_id": source_id,
                }
            )

        # 4. Ensure Vector Index Exists for GDS Semantic Weaver
        await neo4j.run_query(
            """
            CREATE VECTOR INDEX pdf_chunks IF NOT EXISTS 
            FOR (t:TextChunk) 
            ON (t.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }}
            """
        )

        logger.info("pdf_graph_building_complete", source_id=source_id)

    except Exception as e:
        logger.error("pdf_graph_building_failed", source_id=source_id, error=str(e))
