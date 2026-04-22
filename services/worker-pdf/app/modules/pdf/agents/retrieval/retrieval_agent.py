import structlog
import uuid
from typing import Dict, Any, List
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.agents.retrieval.cypher_generator_agent import pdf_cypher_generator_agent
from app.modules.pdf.utils.embeddings_wrapper import FastEmbedGraphRagWrapper
from neo4j_graphrag.retrievers import QdrantNeo4jRetriever
from qdrant_client import QdrantClient, models
from neo4j import GraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def adaptive_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """Retrieves document pages using high-performance GraphRAG pattern."""
    question = state.get("question")
    kb_id = state.get("kb_id")
    source_id = state.get("source_id")
    retry_count = state.get("retry_count", 0)
    
    logger.info("adaptive_retrieval_graphrag_started", question=question, retry=retry_count)
    
    # 1. Prepare Connections & Embedder
    embedder = FastEmbedGraphRagWrapper()
    q_client = QdrantClient(url=settings.QDRANT_URL or "http://qdrant:6333")
    
    if kb_id:
        collection_name = f"kb_{str(kb_id).replace('-', '')}"
        filter_condition = models.FieldCondition(key="kb_id", match=models.MatchValue(value=str(kb_id)))
    else:
        collection_name = f"ds_{str(source_id).replace('-', '')}"
        filter_condition = models.FieldCondition(key="source_id", match=models.MatchValue(value=str(source_id)))

    # 2. Dynamic Cypher Generation for Graph Enrichment
    cypher_res = await pdf_cypher_generator_agent(state)
    custom_query = cypher_res.get("cypher_query")
    
    # 3. Initialize & Execute Standardized GraphRAG Retriever
    # This replaces Tier A (Vector) and Tier B (Graph) with a single operation
    try:
        with GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)) as driver:
            retriever = QdrantNeo4jRetriever(
                driver=driver,
                client=q_client,
                collection_name=collection_name,
                id_property_external="id",        # Qdrant point UUID
                id_property_neo4j="chunk_id",      # Neo4j node property
                embedder=embedder,
                retrieval_query=custom_query,     # Unified Graph-Vector logic
                node_label_neo4j="Chunk"
            )
            
            # Execute Hybrid Search
            # We pass the metadata filter to ensure we only search the current KB/Source
            raw_results = await retriever.asearch(
                query_text=question, 
                top_k=15,
                filter=models.Filter(must=[filter_condition])
            )
            
            records = raw_results.records
            
    except Exception as e:
        logger.error("graphrag_retrieval_failed", error=str(e))
        records = []

    # 4. Format Results for Analyst
    vector_hits = []
    graph_insights = []
    page_nums = []

    for record in records:
        # Standard neo4j-graphrag results map back to the 'node' or custom return properties
        # Our custom_query dictates the record structure
        if "node" in record:
            node = record["node"]
            vector_hits.append({
                "payload": dict(node),
                "score": record.get("score", 1.0)
            })
            if node.get("page"):
                page_nums.append(node["page"])
        else:
            # Fallback for complex graph insights
            graph_insights.append(dict(record))

    enriched_results = {
        "vector_hits": vector_hits,
        "graph_insights": graph_insights
    }

    # 5. Reflection & Cleanup
    if not vector_hits and not graph_insights:
        if retry_count < 2:
            logger.warning("retrieval_failed_triggering_reflection", retry=retry_count)
            return {"search_results": [], "reflection_needed": True, "retry_count": retry_count + 1}
        else:
            logger.error("retrieval_failed_no_more_retries")
            return {"error": "No relevant data found in Knowledge Graph.", "search_results": []}

    return {
        "search_results": enriched_results, 
        "page_nums": sorted(list(set(page_nums))),
        "reflection_needed": False,
        "executive_summary": f"GraphRAG retrieved {len(vector_hits)} chunks with integrated associative context."
    }
