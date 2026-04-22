from typing import List
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.utils.rate_limit import RetryRateLimitHandler

class FastEmbedGraphRagWrapper(Embedder):
    """Wrapper for nexus to use multilingual-e5-large (1024d)."""
    
    def __init__(self):
        super().__init__()
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        from app.infrastructure.config import settings
        
        self.model = FastEmbedEmbeddings(
            model_name=settings.EMBED_MODEL_GENERAL
        )
        self.rate_limit_handler = RetryRateLimitHandler(
            max_attempts=5, multiplier=2.0
        )

    def embed_query(self, text: str) -> List[float]:
        return self.model.embed_query(text)

    async def async_embed_query(self, text: str) -> List[float]:
        return await self.model.aembed_query(text)
