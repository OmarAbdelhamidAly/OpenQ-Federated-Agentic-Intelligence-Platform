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
        RelationshipType(label="HAS_FUNCTION"),
        RelationshipType(label="CALLS"),
        RelationshipType(label="IMPORTS")
    ],
    patterns=[
        ("Class", "DEFINED_IN", "File"),
        ("Function", "DEFINED_IN", "File"),
        ("Class", "HAS_FUNCTION", "Function"),
        ("Function", "CALLS", "Function"),
        ("File", "IMPORTS", "File")
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
    function_calls_data = payload.get("function_calls", [])
    imports_data = payload.get("imports", [])
    
    if not any([files_data, classes_data, functions_data]):
        logger.warning("code_indexer_empty_payload", source_id=source_id)
        return
        
    adapter = Neo4jAdapter()
    driver = adapter.driver
    graph = Neo4jGraph()
    
    # Track node instances to create relationships easily
    file_nodes = {}
    class_nodes = {}
    function_nodes = {}
    
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
        
        # Unique key for function calls linking
        func_key = func.get("key", f"{file_path}::{class_name}::{name}" if class_name else f"{file_path}::{name}")
        function_nodes[func_key] = node
        
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

    # 4.5 Build Function CALLS Relationships
    for call in function_calls_data:
        caller_key = call.get("caller_key")
        callee_key = call.get("callee_key")
        
        if caller_key in function_nodes and callee_key in function_nodes:
            rel = Relationship(
                type="CALLS",
                start_node=function_nodes[caller_key],
                end_node=function_nodes[callee_key],
                properties={}
            )
            graph.relationships.append(rel)
            
    # 4.6 Build File IMPORTS Relationships
    for imp in imports_data:
        from_file = imp.get("from_file")
        to_file = imp.get("to_file")
        
        if from_file in file_nodes and to_file in file_nodes:
            rel = Relationship(
                type="IMPORTS",
                start_node=file_nodes[from_file],
                end_node=file_nodes[to_file],
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
