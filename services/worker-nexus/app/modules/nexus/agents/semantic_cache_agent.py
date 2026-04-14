"""Semantic Caching Utility for Strategic Nexus."""
import structlog
import uuid
from typing import Any, Dict
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from app.infrastructure.config import settings
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

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

async def save_semantic_cache(state: NexusState) -> Dict[str, Any]:
    """Terminal node that saves final strategic synthesis to the semantic cache."""
    question = state.get("question")
    synthesis = state.get("final_synthesis")
    tenant_id = state.get("tenant_id")
    
    # Save if it's the start of a thread (Experience saving)
    if not state.get("chat_history") and question and synthesis and tenant_id:
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
                        payload={
                            "question": question, 
                            "synthesis": synthesis, 
                            "type": "nexus"
                        }
                    )
                ]
            )
            logger.info("nexus_semantic_cache_saved", tenant_id=tenant_id)
        except Exception as e:
            logger.warning("nexus_semantic_cache_save_failed", error=str(e))
            
    return {}
