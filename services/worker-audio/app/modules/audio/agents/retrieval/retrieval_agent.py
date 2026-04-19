"""Audio Hybrid Retrieval Agent.

Retrieves conversational context using both Vector and Graph tiers.
"""
import asyncio
import structlog
from typing import Dict, Any, List
from app.domain.analysis.entities import AudioAnalysisState
from app.modules.audio.agents.retrieval.cypher_generator_agent import audio_cypher_generator_agent
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from qdrant_client import QdrantClient
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def audio_retrieval_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Retrieves conversation turns via Vector Search and Graph Traversal."""
    source_id = state.get("source_id")
    question = state.get("question")
    
    logger.info("audio_retrieval_started", source_id=source_id)

    # 1. Initialize Vector Tier (Qdrant)
    # Assuming embeddings are generated via a shared utility or inside the agent
    # For now, we'll simulate or use the same model as indexing
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
    
    async def run_vector():
        qdrant = QdrantClient(settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        collection_name = f"audio_{source_id.replace('-', '_')}"
        query_vector = model.encode(question).tolist()
        
        try:
            hits = qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=15
            )
            return hits
        except Exception:
            return []

    # 2. Initialize Graph Tier (Neo4j Cypher)
    async def run_graph():
        cypher_res = await audio_cypher_generator_agent(state)
        query = cypher_res.get("cypher_query")
        if not query:
            return []
        
        neo4j = Neo4jAdapter()
        try:
            return await neo4j.run_query(query, cypher_res.get("cypher_params", {}))
        except Exception as e:
            logger.warning("audio_retrieval_cypher_failed", error=str(e))
            return []

    # Run Hybrid
    vector_results, graph_results = await asyncio.gather(run_vector(), run_graph())
    
    return {
        "retrieval_context": {
            "vector_hits": [h.payload for h in vector_results],
            "graph_insights": graph_results
        }
    }
