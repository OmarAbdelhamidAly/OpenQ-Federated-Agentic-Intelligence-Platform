"""Vector Indexer Agent — LangGraph Node.

Responsible strictly for semantic indexing.
Chunks every speaker turn and inserts them into Qdrant as 768D vectors.
"""
from __future__ import annotations
import uuid
import structlog
from typing import Any, Dict
from app.domain.analysis.entities import AudioAnalysisState

logger = structlog.get_logger(__name__)


async def vector_indexer_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Index speaker turns as searchable semantic vectors in Qdrant."""
    if state.get("error"):
        return {}

    source_id = state.get("source_id", "")
    tenant_id = state.get("tenant_id", "")
    speaker_turns = state.get("speaker_turns", [])

    collection_name = f"audio_{source_id.replace('-', '')}" if source_id else f"audio_{uuid.uuid4().hex}"
    chunks_indexed = 0

    if not speaker_turns:
        return {"qdrant_collection": collection_name, "chunks_indexed": 0}

    try:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from app.infrastructure.config import settings

        embedder = FastEmbedEmbeddings(model_name="nomic-ai/nomic-embed-text-v1.5")
        qdrant = QdrantClient(url=settings.QDRANT_URL)

        # Ensure collection exists
        try:
            qdrant.get_collection(collection_name)
        except Exception:
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

        points = []
        for turn in speaker_turns:
            text = turn.get("text", "").strip()
            if not text or len(text) < 10:
                continue

            # Deterministic Chunk ID (to sync Qdrant with Neo4j)
            chunk_hash_input = f"{source_id}_{turn.get('speaker_id', 'unknown')}_{text[:50]}"
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_hash_input))
            
            vector = embedder.embed_query(text)
            
            # Save chunk_id and embedding back to state so Neo4j can use it natively for GDS
            turn["chunk_id"] = chunk_id
            turn["embedding"] = vector

            points.append(PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "source_id": source_id,
                    "tenant_id": tenant_id,
                    "speaker_id": turn.get("speaker_id", "SPEAKER_01"),
                    "speaker_name": turn.get("speaker_name", turn.get("speaker_id", "")),
                    "text": text,
                    "start_time": turn.get("start_time", 0.0),
                    "end_time": turn.get("end_time", 0.0),
                    "topics": turn.get("topics", []),
                    "pillar": "audio",
                },
            ))

        if points:
            qdrant.upsert(collection_name=collection_name, points=points)
            chunks_indexed = len(points)
            logger.info("audio_qdrant_indexed", chunks=chunks_indexed, collection=collection_name)

    except Exception as e:
        logger.warning("audio_qdrant_failed", error=str(e))

    return {
        "qdrant_collection": collection_name,
        "chunks_indexed": chunks_indexed,
    }
