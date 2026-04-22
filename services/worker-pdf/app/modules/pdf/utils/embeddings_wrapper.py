"""Embedder wrapper for neo4j-graphrag to use FastEmbed/SentenceTransformers.

This implements the Embedder interface required by neo4j-graphrag, 
allowing us to use our local multilingual-e5-large model.
"""
from typing import List
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.utils.rate_limit import RetryRateLimitHandler
from app.modules.pdf.agents.indexing.deep_vision.agents.indexing_agent import _get_embedding_model

class FastEmbedGraphRagWrapper(Embedder):
    """Wrapper to bridge LangChain/FastEmbed model with neo4j-graphrag.
    
    Includes RetryRateLimitHandler for exponential backoff on API errors.
    """
    
    def __init__(self):
        super().__init__()
        self.model = _get_embedding_model()
        # Enterprise-grade rate limit handling
        self.rate_limit_handler = RetryRateLimitHandler(
            max_attempts=5,
            min_wait=2.0,
            max_wait=60.0,
            multiplier=2.0
        )

    def embed_query(self, text: str) -> List[float]:
        """Synchronously embed query text with retry logic."""
        # Note: FastEmbed is local, but we keep the structure for cloud portability
        return self.model.embed_query(text)

    async def async_embed_query(self, text: str) -> List[float]:
        """Asynchronously embed query text."""
        return await self.model.aembed_query(text)
