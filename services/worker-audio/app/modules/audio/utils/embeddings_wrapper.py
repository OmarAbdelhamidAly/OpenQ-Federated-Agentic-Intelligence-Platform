"""Embedder wrapper for neo4j-graphrag in worker-audio."""
from typing import List
from neo4j_graphrag.embeddings.base import Embedder
from app.modules.audio.agents.retrieval.retrieval_agent import _get_embedding_model

class FastEmbedGraphRagWrapper(Embedder):
    """Wrapper to bridge LangChain/FastEmbed model with neo4j-graphrag."""
    
    def __init__(self):
        super().__init__()
        self.model = _get_embedding_model()

    def embed_query(self, text: str) -> List[float]:
        """Synchronously embed query text."""
        return self.model.embed_query(text)

    async def async_embed_query(self, text: str) -> List[float]:
        """Asynchronously embed query text."""
        # For compatibility with audio retrieval agent
        return self.model.embed_query(text) 
