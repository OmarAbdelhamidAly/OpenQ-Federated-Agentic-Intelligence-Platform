"""Audio Indexer for Neo4j GraphRAG (Federated Sink).
Acts as a pure aggregator. Receives fully processed chunks (Turns) 
from worker-audio and builds the Knowledge Graph using neo4j-graphrag's LexicalGraphBuilder and Neo4jWriter.
"""
import uuid
import structlog
from typing import Dict, Any

from neo4j_graphrag.experimental.pipeline.kg_builder import LexicalGraphBuilder, LexicalGraphConfig
from neo4j_graphrag.experimental.components.kg_writer import Neo4jWriter
from neo4j_graphrag.experimental.pipeline.data_models import Neo4jGraph, Node
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

async def index_audio_content(payload: Dict[str, Any]) -> None:
    """Sink for Audio Knowledge Graph construction.
    
    Expected payload format:
    {
        "source_id": "audio_123",
        "metadata": {"title": "Meeting Recording", "date": "..."},
        "chunks": [  # (Turns)
            {
                "id": "uuid5-hash-1", 
                "text": "Speaker A: Hello...", 
                "embedding": [...], 
                "entities": [
                    {"name": "Speaker A", "type": "Speaker"},
                    {"name": "Project X", "type": "Project"}
                ]
            },
            ...
        ]
    }
    """
    source_id = payload.get("source_id", f"audio_{uuid.uuid4().hex[:8]}")
    metadata = payload.get("metadata", {})
    chunks_data = payload.get("chunks", [])
    
    logger.info("audio_indexer_sink_started", source_id=source_id, chunk_count=len(chunks_data))
    
    if not chunks_data:
        logger.warning("audio_indexer_empty_payload", source_id=source_id)
        return
        
    adapter = Neo4jAdapter()
    driver = adapter.driver
    
    # 1. Configuration
    config = LexicalGraphConfig(
        document_node_label='AudioSession',
        chunk_node_label='Turn',
        chunk_to_document_relationship_type='FROM_SESSION',
        next_chunk_relationship_type='NEXT_TURN',
        node_to_chunk_relationship_type='MENTIONS',
        chunk_id_property='id',
        chunk_text_property='text',
        chunk_embedding_property='embedding'
    )
    
    builder = LexicalGraphBuilder(config=config)
    graph = Neo4jGraph()
    
    # 2. Build Document Node
    document_info = {"id": source_id, "source_id": source_id, **metadata}
    doc_node = builder.create_document_node(document_info)
    graph.nodes.append(doc_node)
    
    # 3. Build Chunks and Topology
    prev_chunk_node = None
    
    for chunk_data in chunks_data:
        chunk_info = {
            "id": chunk_data.get("id"),
            "text": chunk_data.get("text"),
            "embedding": chunk_data.get("embedding"),
            "source_id": source_id
        }
        chunk_node = builder.create_chunk_node(chunk_info)
        graph.nodes.append(chunk_node)
        
        # Link Chunk -> Document
        rel_to_doc = builder.create_chunk_to_document_rel(chunk_info, document_info)
        graph.relationships.append(rel_to_doc)
        
        # Link Chunk -> Previous Chunk
        if prev_chunk_node:
            rel_next = builder.create_next_chunk_relationship(
                prev_chunk_node.properties, 
                chunk_node.properties
            )
            graph.relationships.append(rel_next)
        
        # 4. Attach Pre-extracted Entities and Speakers
        entities = chunk_data.get("entities", [])
        for ent in entities:
            ent_label = ent.get("type", "Entity")
            ent_name = ent.get("name")
            
            entity_node = Node(
                label=ent_label,
                properties={"name": ent_name, "source_id": source_id}
            )
            graph.nodes.append(entity_node)
            
            if ent_label == "Speaker":
                rel = Relationship(
                    type="SPOKE",
                    start_node=entity_node,
                    end_node=chunk_node,
                    properties={}
                )
                graph.relationships.append(rel)
            else:
                rel_to_ent = builder.create_node_to_chunk_rel(entity_node, chunk_info["id"])
                graph.relationships.append(rel_to_ent)
            
        prev_chunk_node = chunk_node

    # 5. Write to Database Safely
    writer = Neo4jWriter(driver=driver, batch_size=500, clean_db=False)
    
    try:
        writer_model = await writer.run(graph=graph, lexical_graph_config=config)
        logger.info("audio_indexer_sink_completed", source_id=source_id, stats=writer_model)
    except Exception as e:
        logger.error("audio_indexer_sink_failed", source_id=source_id, error=str(e))
