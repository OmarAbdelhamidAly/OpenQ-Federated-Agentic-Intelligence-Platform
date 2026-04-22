"""Knowledge Cleaner Agent — Entity Resolution.

Uses FuzzyMatchResolver from neo4j-graphrag to identify and merge 
duplicate entity nodes (e.g., 'Apple' and 'Apple Inc.') across the 
entire knowledge graph.
"""
import structlog
from neo4j import GraphDatabase
from neo4j_graphrag.experimental.components.resolver import FuzzyMatchResolver
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def run_entity_resolution(similarity_threshold: float = 0.85):
    """Scan and merge duplicate Entity nodes in Neo4j."""
    logger.info("entity_resolution_started", threshold=similarity_threshold)
    
    try:
        with GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        ) as driver:
            
            # Initialize the resolver for 'Entity' nodes
            resolver = FuzzyMatchResolver(
                driver=driver,
                similarity_threshold=similarity_threshold
            )
            
            # Execute the resolution/merge logic
            # This identifies nodes with similar 'name' properties and merges them
            result = await resolver.run()
            
            logger.info(
                "entity_resolution_completed", 
                nodes_compared=result.get("nodes_compared", 0),
                matches_found=result.get("matches_found", 0)
            )
            return result
            
    except Exception as e:
        logger.error("entity_resolution_failed", error=str(e))
        return {"error": str(e)}

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_entity_resolution())
