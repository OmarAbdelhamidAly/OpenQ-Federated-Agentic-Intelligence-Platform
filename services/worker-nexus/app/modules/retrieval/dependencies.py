from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from neo4j_graphrag.llm import RetryRateLimitHandler
from app.infrastructure.config import settings

_neo4j_driver = None
_qdrant_client = None
_rate_limiter = None

def get_neo4j_driver():
    """Lazy sync Neo4j driver for neo4j-graphrag library (requires sync driver)."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
        )
    return _neo4j_driver

def get_qdrant_client():
    """Lazy Qdrant client using settings (not hardcoded host)."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
    return _qdrant_client

def get_rate_limiter():
    """Shared rate limiter to prevent LLM API 429s across different retrievers."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RetryRateLimitHandler(max_attempts=3, jitter=True)
    return _rate_limiter
