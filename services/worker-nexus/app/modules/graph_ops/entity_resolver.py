"""Entity Resolver for Autonomous Cross-Pillar Linking.
Merges duplicate or highly similar entities across different sources.
"""
import asyncio
import structlog
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from neo4j_graphrag.experimental.components.resolver import FuzzyMatchResolver

logger = structlog.get_logger(__name__)

async def run_entity_resolution() -> dict:
    """Run fuzzy matching to merge similar entities across the Graph."""
    logger.info("entity_resolution_started")
    adapter = Neo4jAdapter()

    # FuzzyMatchResolver uses RapidFuzz under the hood.
    resolver = FuzzyMatchResolver(
        driver=adapter.driver,
        resolve_properties=["name", "title"],
        similarity_threshold=0.85
    )

    try:
        # get_running_loop() is the correct call inside an async context (Python 3.10+).
        # get_event_loop() is deprecated and emits DeprecationWarning in 3.11.
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, resolver.run)

        logger.info("entity_resolution_completed", stats=str(stats))
        return {"status": "success", "stats": str(stats)}
    except Exception as e:
        logger.error("entity_resolution_failed", error=str(e))
        return {"status": "error", "error": str(e)}

