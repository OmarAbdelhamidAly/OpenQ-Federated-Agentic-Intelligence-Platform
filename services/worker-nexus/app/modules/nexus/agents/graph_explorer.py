"""Nexus Graph Explorer Agent — Knowledge Discovery."""
from typing import Dict, Any, List
import structlog
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

async def graph_explorer(state: NexusState) -> Dict[str, Any]:
    """Crawl the Neo4j UKG to find paths between the selected sources."""
    neo4j = Neo4jAdapter()
    source_ids = state["source_ids"]
    
    discovery_logs = []
    
    # 1. Run the "Nexus Bridge" if not already run (idempotent)
    for sid in source_ids:
        await neo4j.execute_nexus_bridge(sid)
    
    # 2. Query for cross-source links (Mentions, Represents Data, etc.)
    links_query = """
    MATCH (n)-[r]->(m)
    WHERE n.source_id IN $source_ids AND m.source_id IN $source_ids
      AND n.source_id <> m.source_id
    RETURN labels(n)[0] AS source_type, n.name AS source_name, 
           type(r) AS rel, 
           labels(m)[0] AS target_type, m.name AS target_name
    LIMIT 20
    """
    
    paths = await neo4j.execute_cypher(links_query, {"source_ids": source_ids})
    
    for p in paths:
        log = f"Found Link: {p['source_type']}({p['source_name']}) --[{p['rel']}]--> {p['target_type']}({p['target_name']})"
        discovery_logs.append(log)
        
    if not discovery_logs:
        discovery_logs.append("No direct cross-pillar relationships found in the knowledge graph yet.")
        
    logger.info("nexus_graph_explored", links_found=len(discovery_logs))
    return {"discovery_logs": discovery_logs}
