"""Semantic Weaver (Graph Data Science) for Codebase Analysis.

Executes native Neo4j GDS algorithms:
1. k-NN Semantic Similarities between Functions and Classes
2. Louvain Modularity for Module/Microservice boundary detection
3. PageRank for determining Core Architectural Components

This runs post-ingestion to enrich the static code graph.
"""
import structlog
from typing import Any
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)


async def run_code_semantic_weaver(source_id: str) -> None:
    """Run GraphRAG GDS algorithms to weave an intelligent software architecture graph."""
    logger.info("code_semantic_weaver_started", source_id=source_id)
    adapter = Neo4jAdapter()

    try:
        # Step 1: Node Similarity (k-NN on Vector Index)
        # Create SIMILAR_TO edges between Functions that have highly similar logic/summaries
        logger.info("code_weaver_knn_graph", source_id=source_id)
        async with adapter.driver.session() as session:
            await session.run(
                """
                MATCH (fn:Function {source_id: $source_id})
                CALL db.index.vector.queryNodes('code_function_embeddings', 5, fn.embedding) YIELD node AS neighbor, score
                WHERE fn <> neighbor AND score > 0.88
                MERGE (fn)-[r:SEMANTICALLY_SIMILAR]->(neighbor)
                SET r.score = score
                """,
                {"source_id": source_id}
            )

        # Step 2: Community Detection (Louvain)
        # We project the graph including [:CALLS] and [:SEMANTICALLY_SIMILAR] to find Modules
        logger.info("code_weaver_louvain_modules", source_id=source_id)
        graph_name = f"code_graph_{source_id.replace('-', '_')}"
        
        async with adapter.driver.session() as session:
            # Drop if exists
            await session.run("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": graph_name})

            # Project Graph (Functions + Calling Topology + Semantic Topology)
            await session.run(
                """
                MATCH (source:Function {source_id: $source_id})
                OPTIONAL MATCH (source)-[r:CALLS|SEMANTICALLY_SIMILAR]->(target:Function {source_id: $source_id})
                WITH gds.graph.project(
                  $graph_name,
                  source,
                  target,
                  { relationshipProperties: r.score }
                ) AS g
                RETURN g.graphName
                """,
                {"source_id": source_id, "graph_name": graph_name}
            )

            # Detect boundaries (Modules/Microservices)
            await session.run(
                """
                CALL gds.louvain.write($graph_name, {
                    writeProperty: 'architectural_module_id'
                }) YIELD communityCount
                """,
                {"graph_name": graph_name}
            )

        # Step 3: Centrality (PageRank) for Core Component Identification
        # A class or function called frequently (or called by highly central components) gets a high score
        logger.info("code_weaver_pagerank_centrality", source_id=source_id)
        pr_graph_name = f"deps_{source_id.replace('-', '_')}"
        
        async with adapter.driver.session() as session:
            await session.run("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": pr_graph_name})

            # Project classes/functions based on explicit calls and definitions
            await session.run(
                """
                MATCH (source {source_id: $source_id})
                WHERE source:Function OR source:Class OR source:File
                OPTIONAL MATCH (source)-[r:CALLS|DEPENDS_ON|DEFINES]->(target)
                WHERE target:Function OR target:Class OR target:File
                WITH gds.graph.project(
                  $graph_name,
                  source,
                  target
                ) AS g
                RETURN g.graphName
                """,
                {"source_id": source_id, "graph_name": pr_graph_name}
            )

            # Write architectural_importance
            await session.run(
                """
                CALL gds.pageRank.write($graph_name, {
                    maxIterations: 20,
                    dampingFactor: 0.85,
                    writeProperty: 'architectural_importance'
                }) YIELD computeMillis
                """,
                {"graph_name": pr_graph_name}
            )

            # Clean up
            await session.run("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": graph_name})
            await session.run("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": pr_graph_name})

        logger.info("code_semantic_weaver_completed", source_id=source_id)

    except Exception as e:
        logger.error("code_semantic_weaver_failed", source_id=source_id, error=str(e))
