"""Audio Hybrid Retrieval Agent.

Retrieves conversational context using both Vector and Graph tiers.

Fix: Aligned embedding model with indexing (multilingual-e5-large, 1024d).
Fix: Switched from QDRANT_HOST/PORT to QDRANT_URL (consistent with all workers).
"""
from __future__ import annotations
import asyncio
import structlog
from typing import Dict, Any, List
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from qdrant_client import QdrantClient
from app.domain.analysis.entities import AudioAnalysisState
from app.modules.audio.agents.retrieval.cypher_generator_agent import audio_cypher_generator_agent
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

# ── Lazy singleton — must match the indexing model exactly ─────────────────────
_embed_model = None

def _get_embed_model() -> FastEmbedEmbeddings:
    """Returns the same multilingual-e5-large model used during indexing (1024d)."""
    global _embed_model
    if _embed_model is None:
        _embed_model = FastEmbedEmbeddings(
            model_name=settings.EMBED_MODEL_GENERAL  # intfloat/multilingual-e5-large — 1024d
        )
    return _embed_model


import structlog
import asyncio
from typing import Dict, Any, List
from app.domain.analysis.entities import AudioAnalysisState
from app.modules.audio.agents.retrieval.cypher_generator_agent import audio_cypher_generator_agent
from app.modules.audio.utils.embeddings_wrapper import FastEmbedGraphRagWrapper
from neo4j_graphrag.retrievers import QdrantNeo4jRetriever
from qdrant_client import QdrantClient, models
from neo4j import GraphDatabase
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def audio_retrieval_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Retrieves conversation turns via high-performance GraphRAG pattern."""
    source_id = state.get("source_id")
    question = state.get("question")

    if not source_id or not question:
        return {"retrieval_context": {"vector_hits": [], "graph_insights": []}}

    logger.info("audio_retrieval_graphrag_started", source_id=source_id)

    # 1. Prepare Connections & Embedder
    embedder = FastEmbedGraphRagWrapper()
    q_client = QdrantClient(url=settings.QDRANT_URL)
    collection_name = f"audio_{source_id.replace('-', '')}"

    # 2. Dynamic Cypher Generation (Turn associations, entities, topics)
    cypher_res = await audio_cypher_generator_agent(state)
    query = cypher_res.get("cypher_query")

    # 3. Synchronized Hybrid Retrieval
    try:
        with GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)) as driver:
            retriever = QdrantNeo4jRetriever(
                driver=driver,
                client=q_client,
                collection_name=collection_name,
                id_property_external="id",        # Qdrant UUID
                id_property_neo4j="chunk_id",      # Neo4j property
                embedder=embedder,
                retrieval_query=query,            # Native graph enrichment
                node_label_neo4j="SpeakerTurn"
            )

            # Retrieve with source-level isolation filter
            raw_results = await retriever.asearch(
                query_text=question,
                top_k=15,
                filter=models.Filter(
                    must=[models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id))]
                )
            )
            records = raw_results.records
    except Exception as e:
        logger.error("audio_graphrag_failed", error=str(e))
        records = []

    # 4. Result Formatting
    vector_hits = []
    graph_insights = []

    for record in records:
        if "node" in record:
            node = record["node"]
            vector_hits.append({
                "text": node.get("text", ""),
                "speaker": node.get("speaker_id", "Unknown"),
                "start_time": node.get("start_time", 0.0),
                "score": record.get("score", 1.0)
            })
        else:
            graph_insights.append(dict(record))

    return {
        "retrieval_context": {
            "vector_hits": vector_hits,
            "graph_insights": graph_insights,
        }
    }
