"""Semantic Caching Utility for Code Worker."""
import structlog
import uuid
from typing import Any, Dict
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from app.infrastructure.config import settings
from app.domain.analysis.entities import CodeAnalysisState

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

async def save_semantic_cache(state: CodeAnalysisState) -> Dict[str, Any]:
    """Saves successful Cypher query and results to semantic cache."""
    question = state.get("question")
    answer = state.get("insight_report")
    cypher = state.get("cypher_query")
    tenant_id = state.get("tenant_id")
    source_id = state.get("source_id", "default")

    if not state.get("chat_history") and question and answer and tenant_id:
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
                        payload={
                            "question": question,
                            "answer": answer,
                            "cypher": cypher,
                            "source_id": source_id,
                            "type": "code",
                        },
                    )
                ],
            )
            logger.info("semantic_cache_saved_code", tenant_id=tenant_id, source_id=source_id)
        except Exception as e:
            logger.warning("semantic_cache_save_failed_code", error=str(e))

    return {}
