"""PDF Semantic Weaver — Graph Data Science Orchestrator.

Executes native Neo4j GDS algorithms for PDFs:
1. k-NN Semantic Similarities between Text Chunks.
2. Louvain Community Detection to group related book/report sections.
3. PageRank for determining the most referenced/central entities.
4. Hierarchical Community Summarization.
"""
import structlog
from typing import Any
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from langchain_openai import ChatOpenAI
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def run_pdf_semantic_weaver(source_id: str) -> None:
    """Run GraphRAG GDS algorithms to weave a semantic document topology."""
    logger.info("pdf_semantic_weaver_started", source_id=source_id)
    adapter = Neo4jAdapter()

    try:
        # Step 1: Node Similarity (k-NN on Vector Index)
        logger.info("pdf_weaver_knn_graph", source_id=source_id)
        await adapter.run_query(
            """
            MATCH (t:TextChunk)-[:PART_OF_DOCUMENT]->(d:DocumentSource {source_id: $source_id})
            CALL db.index.vector.queryNodes('pdf_chunks', 5, t.embedding) YIELD node AS neighbor, score
            WHERE t <> neighbor AND score > 0.88
            MERGE (t)-[r:SIMILAR_TO]->(neighbor)
            SET r.score = score
            """,
            {"source_id": source_id}
        )

        # Step 2: Community Detection (Louvain)
        logger.info("pdf_weaver_louvain_communities", source_id=source_id)
        graph_name = f"pdf_graph_{source_id.replace('-', '_')}"
        
        # Cleanup
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": graph_name})

        # Project Chunks and Similarity edges
        await adapter.run_query(
            """
            MATCH (t:TextChunk)-[:PART_OF_DOCUMENT]->(d:DocumentSource {source_id: $source_id})
            OPTIONAL MATCH (t)-[r:SIMILAR_TO]->(t2)
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

        # Run Louvain
        await adapter.run_query(
            """
            CALL gds.louvain.write($graph_name, {
                writeProperty: 'community_id'
            }) YIELD communityCount
            """,
            {"graph_name": graph_name}
        )

        # Step 3: Centrality (PageRank) for Entities
        logger.info("pdf_weaver_pagerank_entities", source_id=source_id)
        entity_graph_name = f"pdf_entities_{source_id.replace('-', '_')}"
        
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": entity_graph_name})

        await adapter.run_query(
            """
            MATCH (e:Entity)-[:MENTIONED_IN]->(d:DocumentSource {source_id: $source_id})
            MATCH (t)-[:MENTIONS]->(e)
            WITH gds.graph.project($graph_name, e, t) AS g
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

        # Step 4: Hierarchical Summarization (The "GraphRAG" part)
        logger.info("pdf_weaver_community_summarization", source_id=source_id)
        llm = ChatOpenAI(
            model="meta-llama/llama-3.1-8b-instruct",
            temperature=0,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )

        # Get all communities
        communities = await adapter.run_query(
            """
            MATCH (t:TextChunk)-[:PART_OF_DOCUMENT]->(d:DocumentSource {source_id: $source_id})
            WITH t.community_id AS comm_id, collect(t.text) AS texts
            RETURN comm_id, texts
            """,
            {"source_id": source_id}
        )

        for comm in communities:
            comm_id = comm["comm_id"]
            texts = comm["texts"]
            combined_text = "\n\n".join(texts)[:6000] # Cap per community
            
            prompt = f"Summarize this topical community from a PDF document. Focus on common themes and key facts.\n\nTexts:\n{combined_text}"
            res = await llm.ainvoke(prompt)
            summary = res.content
            
            await adapter.run_query(
                """
                MERGE (c:CommunitySummary {community_id: $comm_id, source_id: $source_id})
                SET c.text = $summary
                WITH c
                MATCH (t:TextChunk {community_id: $comm_id})
                WHERE (t)-[:PART_OF_DOCUMENT]->(:DocumentSource {source_id: $source_id})
                MERGE (c)-[:SUMMARIZES]->(t)
                """,
                {"comm_id": comm_id, "source_id": source_id, "summary": summary}
            )

        # Cleanup RAM
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": graph_name})
        await adapter.run_query("""CALL gds.graph.drop($graph_name, false) YIELD graphName""", {"graph_name": entity_graph_name})

        logger.info("pdf_semantic_weaver_completed", source_id=source_id)

    except Exception as e:
        logger.error("pdf_semantic_weaver_failed", source_id=source_id, error=str(e))
