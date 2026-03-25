"""Semantic Caching Agent for intercepting identical queries."""
import structlog
from typing import Any, Dict
from qdrant_client import AsyncQdrantClient
import uuid
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding
from app.infrastructure.config import settings
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

# Maintain stateless singleton to avoid reloading fastembed model
_embed_model = None
def get_embedding_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(model_name="intfloat/multilingual-e5-small")
    return _embed_model

def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    return [float(x) for x in embeddings[0]]

async def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

async def check_cache(question: str, tenant_id: str, source_id: str) -> str | None:
    """Checks vector cache for >95% similarity match. Returns the cached answer if found."""
    try:
        client = await get_qdrant()
        col_name = f"cache_{tenant_id.replace('-', '_')}"
        
        if not await client.collection_exists(col_name):
            return None
            
        vector = embed_text(question)
        hits = await client.search(
            collection_name=col_name,
            query_vector=vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="source_id", match=MatchValue(value=source_id))
                ]
            ),
            limit=1,
            score_threshold=0.95
        )
        if hits:
            logger.info("semantic_cache_hit", score=hits[0].score, tenant_id=tenant_id, source_id=source_id)
            return hits[0].payload.get("answer")
            
    except Exception as e:
        logger.warning("semantic_cache_read_failed", error=str(e))
    return None


async def save_cache(question: str, answer: str, tenant_id: str, source_id: str):
    """Saves a question-answer pair to the vector cache."""
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

async def semantic_cache_agent(state: AnalysisState) -> Dict[str, Any]:
    """Node that checks the cache. 
    If a hit is found, it mimics the clarification pattern to trigger the fast-track bypass."""
    
    question = state.get("question")
    tenant_id = state.get("tenant_id")
    
    # Do not cache hits if chat history is active to avoid confusing context overlaps
    if question and tenant_id and not state.get("history"):
        cached_answer = await check_cache(question, tenant_id, state.get("source_id", "default"))
        if cached_answer:
            return {
                "clarification_needed": f"[Cached Result] {cached_answer}",
                "intent": "cache_hit"
            }
            
    return {"intent": "cache_miss"}
