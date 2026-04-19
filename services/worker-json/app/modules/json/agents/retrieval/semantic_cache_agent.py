"""Semantic Caching Utility for JSON Worker — Allows saving results to the global cache."""
import structlog
import uuid
from typing import Any, Dict
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from app.infrastructure.config import settings
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

# Maintain stateless singleton to avoid reloading fastembed model
_embed_model = None
def get_embedding_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embed_model

def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    return [float(x) for x in embeddings[0]]

async def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

async def save_semantic_cache(state: AnalysisState) -> Dict[str, Any]:
    """Terminal node that saves the final insight report to the semantic cache if no history is present."""
    question = state.get("question")
    answer = state.get("insight_report")
    tenant_id = state.get("tenant_id")
    source_id = state.get("source_id", "default")
    
    # Only cache if we have a valid question/answer and it's not a multi-turn conversation
    if not state.get("history") and question and answer and tenant_id:
        try:
            client = await get_qdrant()
            col_name = f"cache_{tenant_id.replace('-', '_')}"
            
            if not await client.collection_exists(col_name):
                await client.create_collection(
                    collection_name=col_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
                
            vector = embed_text(question)
            await client.upsert(
                collection_name=col_name,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={"question": question, "answer": answer, "source_id": source_id}
                    )
                ]
            )
            logger.info("semantic_cache_saved", tenant_id=tenant_id, source_id=source_id)
        except Exception as e:
            logger.warning("semantic_cache_save_failed", error=str(e))
            
    return {}
