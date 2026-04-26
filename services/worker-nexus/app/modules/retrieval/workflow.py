import os
import json
import uuid
import asyncio
import structlog
from typing import Any, Dict, List

from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

# Infrastructure imports
from app.infrastructure.config import settings
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.llm import get_llm
from app.schemas.nexus_state import NexusState

# GraphRAG imports — sync driver required by neo4j-graphrag library
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from neo4j_graphrag.retrieval import ToolsRetriever, Text2CypherRetriever, QdrantNeo4jRetriever
from neo4j_graphrag.llm import OpenAILLM, RetryRateLimitHandler
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.generation.prompts import RagTemplate
from neo4j_graphrag.memory import Neo4jMessageHistory

logger = structlog.get_logger(__name__)

# ── Global Resource Initialization (lazy singletons) ─────────────────────────
# These are module-level to avoid rebuilding expensive connections on every node.
# BUG-FIX: was settings.NEO4J_USER — correct field name is NEO4J_USERNAME.
_neo4j_driver = None
_qdrant_client = None
_rate_limiter = None


def _get_neo4j_driver():
    """Lazy sync Neo4j driver for neo4j-graphrag library (requires sync driver)."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
        )
    return _neo4j_driver


def _get_qdrant_client():
    """Lazy Qdrant client using settings (not hardcoded host)."""
    global _qdrant_client
    if _qdrant_client is None:
        # QDRANT_URL format: http://host:port
        qdrant_url = settings.QDRANT_URL
        _qdrant_client = QdrantClient(url=qdrant_url, api_key=settings.QDRANT_API_KEY or None)
    return _qdrant_client


def _get_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RetryRateLimitHandler(max_attempts=3, jitter=True)
    return _rate_limiter


# ─── Node 0: Semantic Query Decomposition ────────────────────────────────────

async def query_fusion_node(state: NexusState) -> Dict[str, Any]:
    """Break down a complex user question into 3 domain-targeted sub-queries."""
    log = logger.bind(job_id=state.get("job_id"), node="query_fusion")
    log.info("decomposing_strategic_intent")

    llm = get_llm(temperature=0, model=settings.LLM_MODEL_NEXUS)

    parser = JsonOutputParser()
    prompt = PromptTemplate(
        template="""You are an Expert System Architect. Break down this question into 3 targeted sub-queries:
        1. Structural (Code/Architecture)
        2. Data Schema (SQL/Tables)
        3. Business Logic (Documents/Policy)

        Question: {question}
        {format_instructions}""",
        input_variables=["question"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    try:
        chain = prompt | llm | parser
        queries = await chain.ainvoke({"question": state["question"]})
        if not isinstance(queries, list):
            queries = [state["question"]]
    except Exception as e:
        log.warning("fusion_parsing_failed", error=str(e))
        queries = [state["question"]]

    return {
        "fusion_queries": queries,
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "Strategic Intent Breakdown",
            "status": f"Generated {len(queries)} specialized sub-queries",
            "timestamp": str(uuid.uuid4())
        }]
    }


# ─── Node 1: Parallel Context Gathering (Cross-DB) ───────────────────────────

async def gather_context_node(state: NexusState) -> Dict[str, Any]:
    """Fetch data from Neo4j & Postgres in parallel to minimise latency."""
    log = logger.bind(job_id=state.get("job_id"), node="gather_context")

    adapter = Neo4jAdapter()
    source_ids = state.get("source_ids", [])

    async def fetch_postgres_meta() -> Dict[str, Any]:
        # BUG-FIX: was importing a non-existent module. Now uses the proper
        # database module created in app/infrastructure/database.py.
        from app.infrastructure.database import async_session_factory
        from sqlalchemy import text
        meta: Dict[str, Any] = {}
        try:
            async with async_session_factory() as session:
                for sid in source_ids:
                    res = await session.execute(
                        text("SELECT type, file_path, schema_json FROM data_sources WHERE id = :sid"),
                        {"sid": sid}
                    )
                    row = res.fetchone()
                    if row:
                        meta[sid] = {"type": row[0], "path": row[1], "schema": row[2] or {}}
        except Exception as e:
            log.error("postgres_meta_failed", error=str(e))
        return meta

    # Execute both DB calls concurrently
    graph_data, meta_data = await asyncio.gather(
        adapter.fetch_multi_source_context(source_ids),
        fetch_postgres_meta(),
    )

    return {
        "graph_context": graph_data,
        "meta_context": meta_data,
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "Cross-Pillar Aggregator",
            "status": f"Collected graph context and metadata for {len(meta_data)} sources",
            "timestamp": str(uuid.uuid4())
        }]
    }


# ─── Node 2: Agentic Multi-Tool Retrieval ────────────────────────────────────

async def rerank_context_node(state: NexusState) -> Dict[str, Any]:
    """Use ToolsRetriever to decide: vector search vs Cypher structural search."""
    log = logger.bind(job_id=state["job_id"], node="agentic_retrieval")

    from app.modules.retrieval.embeddings_wrapper import FastEmbedGraphRagWrapper
    embedder = FastEmbedGraphRagWrapper()

    neo4j_driver = _get_neo4j_driver()
    qdrant_client = _get_qdrant_client()
    rate_limiter = _get_rate_limiter()

    graphrag_llm = OpenAILLM(
        model_name=settings.LLM_MODEL_NEXUS,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        rate_limit_handler=rate_limiter,
    )

    # Tool 1: Semantic Search via Qdrant + Neo4j
    vector_retriever = QdrantNeo4jRetriever(
        driver=neo4j_driver,
        client=qdrant_client,
        collection_name="openq_global_vectors",
        id_property_external="neo4j_id",
        embedder=embedder,
    )

    # Tool 2: Structural Cypher Search
    cypher_retriever = Text2CypherRetriever(
        driver=neo4j_driver,
        llm=graphrag_llm,
        neo4j_schema="""
        (Chunk)-[:FROM_DOCUMENT]->(Document), (Class)-[:HAS_FUNCTION]->(Function),
        (Table)-[:HAS_COLUMN]->(Column), (Chunk)-[:INFERRED_LINK_GRL]->(Class)
        """,
    )

    master_retriever = ToolsRetriever(
        driver=neo4j_driver,
        llm=graphrag_llm,
        tools=[
            vector_retriever.convert_to_tool(name="vector_search"),
            cypher_retriever.convert_to_tool(name="graph_structural_search"),
        ],
    )

    # BUG-FIX: master_retriever.search() is synchronous — must offload to thread
    # to avoid blocking the async event loop.
    raw_results = await asyncio.to_thread(
        master_retriever.search, query_text=state["question"]
    )

    top_entities: List[str] = [
        item.content if hasattr(item, "content") else str(item)
        for item in raw_results.items
    ]

    return {
        "reranked_entities": top_entities,
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "Agentic Mastermind",
            "status": "Selected optimal retrieval path (Hybrid Graph + Vector)",
            "timestamp": str(uuid.uuid4())
        }]
    }


# ─── Node 3: Executive Synthesis with Neo4j Memory ───────────────────────────

async def synthesis_node(state: NexusState) -> Dict[str, Any]:
    """Generate the final intelligence report with persistent Neo4j memory."""
    log = logger.bind(job_id=state["job_id"], node="synthesis")

    neo4j_driver = _get_neo4j_driver()
    rate_limiter = _get_rate_limiter()

    graphrag_llm = OpenAILLM(
        model_name=settings.LLM_MODEL_NEXUS,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        rate_limit_handler=rate_limiter,
    )

    # Persistent conversation memory stored in Neo4j (Auditability)
    session_id = f"{state.get('tenant_id', 'global')}_{state['job_id']}"
    history = Neo4jMessageHistory(session_id=session_id, driver=neo4j_driver)

    context_str = "\n".join(state.get("reranked_entities", []))

    rag_template = RagTemplate(template="""
    You are the OpenQ Nexus Intelligence Engine. Use the context below to answer.
    Context consists of: 1) Semantic snippets 2) Knowledge Graph paths.

    <CONTEXT>
    {context}
    </CONTEXT>

    Question: {query_text}
    Answer in a structured format with clear headers.
    """)

    class StaticContextRetriever:
        """Injects pre-retrieved context into the GraphRAG pipeline."""
        def search(self, *args, **kwargs):
            class _Result:
                items = [context_str]
            return _Result()

    rag_pipeline = GraphRAG(
        retriever=StaticContextRetriever(),
        llm=graphrag_llm,
        prompt_template=rag_template,
    )

    try:
        # GraphRAG.search is synchronous — offload to thread pool
        response = await asyncio.to_thread(
            rag_pipeline.search,
            query_text=state["question"],
            message_history=history,
        )
        final_answer = response.answer
    except Exception as e:
        log.error("synthesis_critical_failure", error=str(e))
        final_answer = "Error generating intelligence report."

    return {
        "synthesis": final_answer,
        "status": "done",
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "GraphRAG Executive Layer",
            "status": "Synthesis finalized with cross-pillar attribution",
            "timestamp": str(uuid.uuid4())
        }]
    }


# ─── Graph Compilation ────────────────────────────────────────────────────────

def create_nexus_graph():
    """Build and compile the LangGraph orchestration pipeline."""
    workflow = StateGraph(NexusState)

    workflow.add_node("query_fusion",    query_fusion_node)
    workflow.add_node("gather_context",  gather_context_node)
    workflow.add_node("rerank_context",  rerank_context_node)
    workflow.add_node("synthesis_layer", synthesis_node)

    workflow.set_entry_point("query_fusion")
    workflow.add_edge("query_fusion",    "gather_context")
    workflow.add_edge("gather_context",  "rerank_context")
    workflow.add_edge("rerank_context",  "synthesis_layer")
    workflow.add_edge("synthesis_layer", END)

    return workflow.compile()