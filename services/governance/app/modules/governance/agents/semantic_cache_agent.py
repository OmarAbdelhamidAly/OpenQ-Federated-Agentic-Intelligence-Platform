"""Semantic Caching Agent for intercepting identical queries."""
import structlog
from typing import Any, Dict
from qdrant_client import AsyncQdrantClient
import uuid
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from app.infrastructure.config import settings
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

# ── Lazy singleton — loaded once per worker process ────────────────────────────
_embed_model = None

def get_embedding_model() -> FastEmbedEmbeddings:
    """Returns local FastEmbed nomic model (768d, multilingual, no API cost)."""
    global _embed_model
    if _embed_model is None:
        _embed_model = FastEmbedEmbeddings(
            model_name=settings.EMBED_MODEL_CACHE  # nomic-ai/nomic-embed-text-v1.5
        )
    return _embed_model

def embed_text(text: str) -> list[float]:
    return get_embedding_model().embed_query(text)

async def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.QDRANT_URL)

async def _ensure_cache_collection(client: AsyncQdrantClient, col_name: str) -> None:
    """Creates or auto-migrates the cache collection to the correct dimension (768d)."""
    target_dim = settings.EMBED_DIM_CACHE  # 768
    if await client.collection_exists(col_name):
        info = await client.get_collection(col_name)
        current_dim = info.config.params.vectors.size
        if current_dim != target_dim:
            logger.info(
                "cache_collection_dim_mismatch_recreating",
                collection=col_name,
                old_dim=current_dim,
                new_dim=target_dim,
            )
            await client.delete_collection(col_name)
            await client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
            )
    else:
        await client.create_collection(
            collection_name=col_name,
            vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
        )

async def check_cache(question: str, tenant_id: str, source_id: str) -> str | None:
    """Checks vector cache for >95% similarity match. Returns the cached answer if found."""
    try:
        client = await get_qdrant()
        col_name = f"cache_{tenant_id.replace('-', '_')}"

        if not await client.collection_exists(col_name):
            return None

        vector = embed_text(question)
        hits = await client.query_points(
            collection_name=col_name,
            query=vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="source_id", match=MatchValue(value=source_id))
                ]
            ),
            limit=1,
            score_threshold=0.95,
        )
        hits = hits.points
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
        await _ensure_cache_collection(client, col_name)

        vector = embed_text(question)
        await client.upsert(
            collection_name=col_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"question": question, "answer": answer, "source_id": source_id},
                )
            ],
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
                "intent": "cache_hit",
            }

    return {"intent": "cache_miss"}
