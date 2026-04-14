"""Episodic Memory for Strategic Nexus — Across-pillar experience retrieval."""
import structlog
from typing import Any, Dict, List
from app.modules.nexus.agents.semantic_cache_agent import get_qdrant, embed_text

logger = structlog.get_logger("app.nexus.episodic_memory")

class EpisodicMemory:
    """Manages long-term experience of cross-pillar correlations."""

    async def get_related_insights(self, tenant_id: str, query: str, limit: int = 1) -> List[Dict[str, Any]]:
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
                score_threshold=0.82
            )
            
            insights = []
            for hit in search_result:
                payload = hit.payload or {}
                if payload.get("type") == "nexus":
                    insights.append({
                        "question": payload.get("question", ""),
                        "synthesis": payload.get("synthesis", "")
                    })
            
            if insights:
                logger.info("nexus_episodic_memory_retrieved", count=len(insights), tenant_id=tenant_id)
            return insights
            
        except Exception as e:
            logger.error("nexus_episodic_memory_failed", error=str(e))
            return []

episodic_memory = EpisodicMemory()
