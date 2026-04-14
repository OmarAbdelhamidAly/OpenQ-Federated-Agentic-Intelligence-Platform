"""Episodic Memory for PDF Worker — Persistent Qdrant-backed experience storage."""
import structlog
from typing import Any, Dict, List
from app.modules.pdf.agents.semantic_cache_agent import get_qdrant, embed_text

logger = structlog.get_logger("app.pdf.episodic_memory")

class EpisodicMemory:
    """Manages long-term Episodic memory of successful PDF analyses via semantic vector search."""

    async def get_related_insights(self, tenant_id: str, query: str, limit: int = 1) -> List[Dict[str, Any]]:
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
                score_threshold=0.88 # Very high threshold for PDF synthesis reuse
            )
            
            insights = []
            for hit in search_result:
                payload = hit.payload or {}
                if payload.get("type") == "pdf":
                    insights.append({
                        "question": payload.get("question", ""),
                        "insight": payload.get("insight", ""),
                        "summary": payload.get("summary", ""),
                        "source_id": payload.get("source_id", "")
                    })
            
            if insights:
                logger.info("pdf_episodic_memory_retrieved", count=len(insights), tenant_id=tenant_id)
            return insights
            
        except Exception as e:
            logger.error("pdf_episodic_memory_retrieval_failed", error=str(e))
            return []

episodic_memory = EpisodicMemory()
