import os
import structlog
from neo4j import GraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        logger.info("neo4j_driver_created")
    return _driver

class Neo4jAdapter:
    def __init__(self):
        self.driver = _get_driver()

    def get_graph_data(self, source_id: str) -> dict:
        """Fetch all nodes and relationships for a specific source to build a visual graph."""
        with self.driver.session() as session:
            # 1. Fetch all nodes
            nodes_query = """
            MATCH (n)
            WHERE n.source_id = $source_id
            RETURN id(n) AS id, labels(n)[0] AS type, n.name AS name, n.path AS path, n.summary AS summary
            """
            nodes_result = session.run(nodes_query, source_id=source_id).data()
            
            # 2. Fetch all relationships (internal to the source)
            links_query = """
            MATCH (s)-[r]->(t)
            WHERE s.source_id = $source_id AND t.source_id = $source_id
            RETURN id(s) AS source, id(t) AS target, type(r) AS type
            """
            links_result = session.run(links_query, source_id=source_id).data()
            
            return {
                "nodes": nodes_result,
                "links": links_result
            }
