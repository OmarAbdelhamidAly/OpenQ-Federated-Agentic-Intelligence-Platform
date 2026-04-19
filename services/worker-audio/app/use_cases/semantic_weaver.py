"""Semantic Weaver — Graph Data Science Orchestrator.

Executes native Neo4j GDS algorithms (k-NN Similarity, Louvain Community Detection, PageRank)
after the standard ingestion pipeline has finished mapping the vector and graph data.
"""
import structlog
from typing import Any
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)


async def run_semantic_weaver(source_id: str) -> None:
    """Run GraphRAG algorithms to weave unstructured chunks into a semantic topology."""
    logger.info("semantic_weaver_started", source_id=source_id)
    adapter = Neo4jAdapter()

    try:
        # Step 1: Node Similarity (k-NN on Vector Index)
        # Create SIMILAR_TO edges natively without external processing
        logger.info("semantic_weaver_knn_graph", source_id=source_id)
        await adapter.run_query(
            """
            MATCH (t:SpeakerTurn)-[:PART_OF]->(a:AudioSource {source_id: $source_id})
            CALL db.index.vector.queryNodes('audio_chunks', 5, t.embedding) YIELD node AS neighbor, score
            WHERE t <> neighbor AND score > 0.85
            MERGE (t)-[r:SIMILAR_TO]->(neighbor)
            SET r.score = score
            """,
            {"source_id": source_id}
        )

        # Step 2: Community Detection (Louvain)
        # GDS requires creating an in-memory projected graph first
        logger.info("semantic_weaver_louvain_communities", source_id=source_id)
        graph_name = f"graph_{source_id.replace('-', '_')}"
        
        # Cleanup any old memory graph
        await adapter.run_query("""
            CALL gds.graph.drop($graph_name, false) YIELD graphName
        """, {"graph_name": graph_name})

        # Project Graph (Chunks + Semantic Edges)
        await adapter.run_query(
            """
            MATCH (t:SpeakerTurn)-[:PART_OF]->(a:AudioSource {source_id: $source_id})
            MATCH (t)-[r:SIMILAR_TO]->(t2)
            WITH gds.graph.project(
              $graph_name,
              t,
              t2,
              { relationshipProperties: r.score }
            ) AS g
            RETURN g.graphName
            """,
            {"source_id": source_id, "graph_name": graph_name}
        )

        # Run Louvain and write community_id back to Neo4j
        await adapter.run_query(
            """
            CALL gds.louvain.write($graph_name, {
                writeProperty: 'community_id'
            }) YIELD communityCount
            """,
            {"graph_name": graph_name}
        )

        # Step 3: Centrality (PageRank) for Entities
        logger.info("semantic_weaver_pagerank_entities", source_id=source_id)
        entity_graph_name = f"entities_{source_id.replace('-', '_')}"
        
        await adapter.run_query("""
            CALL gds.graph.drop($graph_name, false) YIELD graphName
        """, {"graph_name": entity_graph_name})

        await adapter.run_query(
            """
            MATCH (e:Entity)-[:MENTIONED_IN]->(a:AudioSource {source_id: $source_id})
            MATCH (t)-[:MENTIONS_ENTITY]->(e)
            WITH gds.graph.project(
              $graph_name,
              e,
              t
            ) AS g
            RETURN g.graphName
            """,
            {"source_id": source_id, "graph_name": entity_graph_name}
        )

        await adapter.run_query(
            """
            CALL gds.pageRank.write($graph_name, {
                maxIterations: 20,
                dampingFactor: 0.85,
                writeProperty: 'pagerank_score'
            }) YIELD computeMillis
            """,
            {"graph_name": entity_graph_name}
        )

        # Clean up graphs from RAM
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": graph_name})
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": entity_graph_name})

        logger.info("semantic_weaver_completed", source_id=source_id)

    except Exception as e:
        logger.error("semantic_weaver_failed", source_id=source_id, error=str(e))
