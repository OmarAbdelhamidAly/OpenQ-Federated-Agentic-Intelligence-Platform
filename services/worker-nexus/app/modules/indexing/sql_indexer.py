"""SQL Indexer for Neo4j GraphRAG (Federated Sink).
Acts as a pure aggregator for Structured Data. Receives SQL schemas
(Tables, Columns) from worker-sql and builds the deterministic Knowledge Graph
using Neo4jWriter.
"""
import structlog
from typing import Dict, Any

from neo4j_graphrag.generation.graph_schema import SchemaBuilder, NodeType, RelationshipType
from neo4j_graphrag.experimental.components.kg_writer import Neo4jWriter
from neo4j_graphrag.experimental.pipeline.data_models import Neo4jGraph, Node, Relationship
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

# 1. Define Strict Deterministic Schema (for documentation and validation)
schema_builder = SchemaBuilder()
sql_schema = schema_builder.run(
    node_types=[
        NodeType(label="Table", properties=[]),
        NodeType(label="Column", properties=[])
    ],
    relationship_types=[
        RelationshipType(label="HAS_COLUMN")
    ],
    patterns=[
        ("Table", "HAS_COLUMN", "Column")
    ]
)

async def index_sql_content(payload: Dict[str, Any]) -> None:
    """Sink for SQL Schema Knowledge Graph construction.
    
    Expected payload format:
    {
        "source_id": "db_123",
        "tables": [{"name": "users"}],
        "columns": [{"name": "id", "table_name": "users", "type": "INTEGER"}]
    }
    """
    source_id = payload.get("source_id", "unknown_db")
    logger.info("sql_indexer_sink_started", source_id=source_id)
    
    tables_data = payload.get("tables", [])
    columns_data = payload.get("columns", [])
    
    if not tables_data and not columns_data:
        logger.warning("sql_indexer_empty_payload", source_id=source_id)
        return
        
    adapter = Neo4jAdapter()
    driver = adapter.driver
    graph = Neo4jGraph()
    
    # Track table nodes
    table_nodes = {}
    
    # 2. Build Table Nodes
    for t in tables_data:
        name = t.get("name")
        node = Node(label="Table", properties={"name": name, "source_id": source_id})
        graph.nodes.append(node)
        table_nodes[name] = node
        
    # 3. Build Column Nodes and Link to Tables
    for c in columns_data:
        name = c.get("name")
        table_name = c.get("table_name")
        data_type = c.get("type", "UNKNOWN")
        
        node = Node(label="Column", properties={
            "name": name, 
            "data_type": data_type, 
            "source_id": source_id
        })
        graph.nodes.append(node)
        
        if table_name and table_name in table_nodes:
            rel = Relationship(
                type="HAS_COLUMN",
                start_node=table_nodes[table_name],
                end_node=node,
                properties={}
            )
            graph.relationships.append(rel)

    # 4. Write to Database Safely (0 seconds LLM latency!)
    writer = Neo4jWriter(driver=driver, batch_size=500, clean_db=False)
    
    try:
        writer_model = await writer.run(graph=graph)
        logger.info("sql_indexer_sink_completed", source_id=source_id, stats=writer_model)
    except Exception as e:
        logger.error("sql_indexer_sink_failed", source_id=source_id, error=str(e))
