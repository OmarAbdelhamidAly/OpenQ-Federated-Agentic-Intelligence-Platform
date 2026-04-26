"""Code Indexer for Neo4j GraphRAG (Federated Sink).
Acts as a pure aggregator for Structured Data. Receives AST components
(Files, Classes, Functions) from worker-code and builds the deterministic Knowledge Graph
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
code_schema = schema_builder.run(
    node_types=[
        NodeType(label="File", properties=[]),
        NodeType(label="Class", properties=[]),
        NodeType(label="Function", properties=[])
    ],
    relationship_types=[
        RelationshipType(label="DEFINED_IN"),
        RelationshipType(label="HAS_FUNCTION")
    ],
    patterns=[
        ("Class", "DEFINED_IN", "File"),
        ("Function", "DEFINED_IN", "File"),
        ("Class", "HAS_FUNCTION", "Function")
    ]
)

async def index_code_content(payload: Dict[str, Any]) -> None:
    """Sink for Code AST Knowledge Graph construction.
    
    Expected payload format:
    {
        "source_id": "repo_123",
        "files": [{"path": "main.py"}],
        "classes": [{"name": "AuthService", "file_path": "main.py"}],
        "functions": [{"name": "login", "file_path": "main.py", "class_name": "AuthService"}]
    }
    """
    source_id = payload.get("source_id", "unknown_repo")
    logger.info("code_indexer_sink_started", source_id=source_id)
    
    files_data = payload.get("files", [])
    classes_data = payload.get("classes", [])
    functions_data = payload.get("functions", [])
    
    if not any([files_data, classes_data, functions_data]):
        logger.warning("code_indexer_empty_payload", source_id=source_id)
        return
        
    adapter = Neo4jAdapter()
    driver = adapter.driver
    graph = Neo4jGraph()
    
    # Track node instances to create relationships easily
    file_nodes = {}
    class_nodes = {}
    
    # 2. Build File Nodes
    for f in files_data:
        path = f.get("path")
        node = Node(label="File", properties={"path": path, "source_id": source_id})
        graph.nodes.append(node)
        file_nodes[path] = node
        
    # 3. Build Class Nodes and Link to Files
    for c in classes_data:
        name = c.get("name")
        file_path = c.get("file_path")
        
        node = Node(label="Class", properties={"name": name, "source_id": source_id})
        graph.nodes.append(node)
        class_nodes[name] = node
        
        if file_path in file_nodes:
            rel = Relationship(
                type="DEFINED_IN",
                start_node=node,
                end_node=file_nodes[file_path],
                properties={}
            )
            graph.relationships.append(rel)
            
    # 4. Build Function Nodes and Link to Files/Classes
    for func in functions_data:
        name = func.get("name")
        file_path = func.get("file_path")
        class_name = func.get("class_name") # Optional
        
        node = Node(label="Function", properties={"name": name, "source_id": source_id})
        graph.nodes.append(node)
        
        if class_name and class_name in class_nodes:
            rel = Relationship(
                type="HAS_FUNCTION",
                start_node=class_nodes[class_name],
                end_node=node,
                properties={}
            )
            graph.relationships.append(rel)
        elif file_path in file_nodes:
            rel = Relationship(
                type="DEFINED_IN",
                start_node=node,
                end_node=file_nodes[file_path],
                properties={}
            )
            graph.relationships.append(rel)

    # 5. Write to Database Safely (0 seconds LLM latency!)
    writer = Neo4jWriter(driver=driver, batch_size=500, clean_db=False)
    
    try:
        writer_model = await writer.run(graph=graph)
        logger.info("code_indexer_sink_completed", source_id=source_id, stats=writer_model)
    except Exception as e:
        logger.error("code_indexer_sink_failed", source_id=source_id, error=str(e))
