"""Episodic Memory for SQL Worker — Persistent Qdrant-backed experience storage."""
import structlog
from typing import Any, Dict, List, Optional
from app.modules.sql.agents.semantic_cache_agent import get_qdrant, embed_text

logger = structlog.get_logger("app.sql.episodic_memory")

class EpisodicMemory:
    """Manages long-term Episodic memory of successful SQL analyses via semantic vector search."""

    async def save_analysis(self, tenant_id: str, source_id: str, question: str, sql: str, insight: str):
        """Delegated to save_semantic_cache node in the workflow, but can be invoked directly if needed."""
        pass # Logic handled gracefully by semantic_cache_agent.py

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
                score_threshold=0.82 # High confidence episodic match
            )
            
            insights = []
            for hit in search_result:
                payload = hit.payload or {}
                insights.append({
                    "question": payload.get("question", ""),
                    "sql": payload.get("sql", "N/A"),
                    "insight": payload.get("answer", "")
                })
            
            if insights:
                logger.info("episodic_memory_retrieved", count=len(insights), tenant_id=tenant_id)
            return insights
            
        except Exception as e:
            logger.error("episodic_memory_retrieval_failed", error=str(e))
            return []

episodic_memory = EpisodicMemory()
