"""Optimized Qdrant Utility — Standardized for 1024d Multilingual RAG.

Removed legacy ColPali multi-vector support to reduce complexity and overhead.
Implemented Production-Grade indexing: HNSW optimizations + Scalar Quantization.
"""
import structlog
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, models
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

class QdrantVectorManager:
    """Manages Qdrant collections for high-performance text RAG."""
    
    def __init__(self, collection_name: str):
        self.client = QdrantClient(url=settings.QDRANT_URL or "http://qdrant:6333")
        self.collection_name = collection_name

    async def ensure_collection(self, vector_size: int = 1024):
        """
        Creates or updates a collection with production-grade indexing parameters.
        Includes auto-migration if dimensions change.
        """
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists:
            # Check for dimension mismatch on the vector
            info = self.client.get_collection(self.collection_name)
            # In simplified mode, vectors is a VectorParams object directly if single, or dict if multiple
            current_vectors = info.config.params.vectors
            
            # Handle both single vector and multi-vector dictionary (for backward compatibility during migration)
            if isinstance(current_vectors, dict):
                current_dim = current_vectors.get("text", {}).size if hasattr(current_vectors.get("text", {}), "size") else None
            else:
                current_dim = current_vectors.size if hasattr(current_vectors, "size") else None

            if current_dim and current_dim != vector_size:
                logger.info(
                    "kb_collection_dim_mismatch_recreating",
                    collection=self.collection_name,
                    old_dim=current_dim,
                    new_dim=vector_size,
                )
                self.client.delete_collection(self.collection_name)
                exists = False

        if not exists:
            logger.info("creating_optimized_production_collection", collection=self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                    on_disk=True # Offload vectors to disk to save RAM
                ),
                # ── HNSW Production Tuning ────────────────────────────────────
                hnsw_config=models.HnswConfigDiff(
                    m=16,              # Standard for high-dim vectors
                    ef_construct=100,  # Good balance between build speed and search quality
                    on_disk=True       # Store HNSW index on disk
                ),
                # ── Scalar Quantization (4x Memory Reduction) ─────────────────
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True # Keep quantized vectors in RAM for speed
                    )
                )
            )

    def upsert(self, point_id: str, vector: List[float], metadata: Dict[str, Any] = {}):
        """Inserts or updates a single point in Qdrant."""
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=metadata
                )
            ]
        )

    def search(self, query_vector: List[float], limit: int = 5, filter: Optional[models.Filter] = None):
        """Performs optimized vector search."""
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter,
            with_payload=True
        )
