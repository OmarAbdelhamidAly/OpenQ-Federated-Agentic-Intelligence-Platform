"""Qdrant HNSW Manager — Single Dense Vector Store for Fast Text RAG.

Used by the Fast Text pipeline (no VLM). Uses BAAI/bge-small-en-v1.5
with HNSW indexing for sub-second retrieval.
"""
from typing import List, Dict, Any, Optional
import structlog
from qdrant_client import QdrantClient, models
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

DENSE_DIM = 384  # BAAI/bge-small-en-v1.5 dimension


class QdrantHNSWManager:
    """Manages a single-vector HNSW Qdrant collection for fast text retrieval."""

    def __init__(self, collection_name: str):
        self.client = QdrantClient(url=settings.QDRANT_URL or "http://qdrant:6333")
        self.collection_name = collection_name

    def ensure_collection(self):
        """Create the collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            logger.info("creating_hnsw_collection", collection=self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=DENSE_DIM,
                    distance=models.Distance.COSINE,
                    on_disk=False,  # Keep in RAM for speed
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=5000,
                ),
            )
            logger.info("hnsw_collection_created", collection=self.collection_name)

    def upsert_chunks(self, points: List[Dict[str, Any]]):
        """Batch upsert text chunks with their dense vectors.
        
        Each point: {"id": str, "vector": List[float], "payload": dict}
        """
        if not points:
            return
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in points
            ],
        )

    def search(
        self,
        query_vector: List[float],
        limit: int = 20,
        filter_payload: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
    ) -> List[models.ScoredPoint]:
        """Dense HNSW search — returns top-k candidates."""
        query_filter = None
        if filter_payload:
            conditions = [
                models.FieldCondition(
                    key=k,
                    match=models.MatchValue(value=v),
                )
                for k, v in filter_payload.items()
            ]
            query_filter = models.Filter(must=conditions)

        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

    def delete_by_source(self, source_id: str):
        """Delete all chunks belonging to a source (for re-indexing)."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id",
                            match=models.MatchValue(value=source_id),
                        )
                    ]
                )
            ),
        )
