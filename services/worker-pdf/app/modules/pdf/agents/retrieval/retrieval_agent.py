import structlog
import uuid
from typing import Dict, Any, List
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.modules.pdf.agents.indexing.deep_vision.agents.indexing_agent import _get_embedding_model
from app.modules.pdf.agents.retrieval.cypher_generator_agent import pdf_cypher_generator_agent
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

async def adaptive_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """Retrieves document pages, with built-in reflection for query adjustment."""
    question = state.get("question")
    kb_id = state.get("kb_id")
    source_id = state.get("source_id")
    retry_count = state.get("retry_count", 0)
    
    logger.info("adaptive_retrieval_started", question=question, retry=retry_count)
    
    # 1. Initialize models and collection
    embed_model = _get_embedding_model()
    
    if kb_id:
        collection_name = f"kb_{str(kb_id).replace('-', '')}"
    else:
        collection_name = f"ds_{str(source_id).replace('-', '')}"
        
    qdrant = QdrantMultiVectorManager(collection_name=collection_name)

    # 2. Parallel Hybrid Retrieval
    import asyncio
    
    # Tier A: Vector Search (Local Context)
    async def run_vector():
        query_vector = embed_model.embed_query(question)
        return qdrant.search_text(query_vector=query_vector, limit=15)
    
    # Tier B: Graph Search (Associative/Global Context)
    async def run_graph():
        cypher_res = await pdf_cypher_generator_agent(state)
        query = cypher_res.get("cypher_query")
        if not query:
            return []
        
        neo4j = Neo4jAdapter()
        try:
            return await neo4j.run_query(query, cypher_res.get("cypher_params", {}))
        except Exception as e:
            logger.warning("retrieval_cypher_failed", error=str(e))
            return []

    # Run both
    vector_results, graph_results = await asyncio.gather(run_vector(), run_graph())
    
    # 3. Merge & Enrich Context
    # We combine vector hits and graph data into a unified structure for the analyst
    enriched_results = {
        "vector_hits": vector_results,
        "graph_insights": graph_results
    }
    
    # 4. Reflection: If no results found in either tier, flag for retry
    if not vector_results and not graph_results:
        if retry_count < 2:
            logger.warning("retrieval_failed_triggering_reflection", retry=retry_count)
            return {"search_results": [], "reflection_needed": True, "retry_count": retry_count + 1}
        else:
            logger.error("retrieval_failed_no_more_retries")
            return {"error": "No relevant pages found after multiple attempts.", "search_results": []}

    # Extract page-level metadata for indexing mode visualization
    page_nums = []
    if vector_results:
        page_nums = [hit.payload.get("page_num") for hit in vector_results if hit.payload.get("page_num")]
    
    return {
        "search_results": enriched_results, 
        "page_nums": sorted(list(set(page_nums))),
        "reflection_needed": False,
        "executive_summary": f"Retrieved {len(vector_results)} chunks and {len(graph_results)} graph associations."
    }
