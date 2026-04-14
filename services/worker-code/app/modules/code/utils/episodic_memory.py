"""Episodic Memory for Code Worker — Persistent Qdrant-backed experience storage."""
import structlog
from typing import Any, Dict, List
from app.modules.code.agents.semantic_cache_agent import get_qdrant, embed_text

logger = structlog.get_logger("app.code.episodic_memory")

class EpisodicMemory:
    """Manages long-term Episodic memory of successful Code analyses via semantic vector search."""

    async def get_related_insights(self, tenant_id: str, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Retrieve past insights semantically related to the user's intent."""
        try:
            client = await get_qdrant()
            col_name = f"cache_{tenant_id.replace('-', '_')}"
            
            if not await client.collection_exists(col_name):
                return []
                
            vector = embed_text(query)
            search_result = await client.search(
                collection_name=col_name,
                query_vector=vector,
                limit=limit,
                score_threshold=0.85 
            )
            
            insights = []
            for hit in search_result:
                payload = hit.payload or {}
                if payload.get("type") == "code":
                    insights.append({
                        "question": payload.get("question", ""),
                        "cypher": payload.get("cypher", "N/A"),
                        "insight": payload.get("answer", "")
                    })
            
            if insights:
                logger.info("code_episodic_memory_retrieved", count=len(insights), tenant_id=tenant_id)
            return insights
            
        except Exception as e:
            logger.error("code_episodic_memory_retrieval_failed", error=str(e))
            return []

episodic_memory = EpisodicMemory()
