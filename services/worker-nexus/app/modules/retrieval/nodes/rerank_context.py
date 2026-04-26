import uuid
import asyncio
import structlog
from typing import Any, Dict, List

from neo4j_graphrag.retrieval import ToolsRetriever, Text2CypherRetriever, QdrantNeo4jRetriever
from neo4j_graphrag.llm import OpenAILLM

from app.infrastructure.config import settings
from app.schemas.nexus_state import NexusState
from app.modules.retrieval.dependencies import get_neo4j_driver, get_qdrant_client, get_rate_limiter
from app.modules.retrieval.embeddings_wrapper import FastEmbedGraphRagWrapper

logger = structlog.get_logger(__name__)

async def rerank_context_node(state: NexusState) -> Dict[str, Any]:
    """Use ToolsRetriever to decide: vector search vs Cypher structural search."""
    log = logger.bind(job_id=state.get("job_id"), node="agentic_retrieval")

    embedder = FastEmbedGraphRagWrapper()

    neo4j_driver = get_neo4j_driver()
    qdrant_client = get_qdrant_client()
    rate_limiter = get_rate_limiter()

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
        (Table)-[:HAS_COLUMN]->(Column), (Column)-[:FOREIGN_KEY_TO]->(Column),
        (Function)-[:CALLS]->(Function), (File)-[:IMPORTS]->(File),
        (Speaker)-[:SPOKE]->(Turn), (Chunk)-[:INFERRED_LINK_GRL]->(Class)
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

    # Execute parallel searches for all fusion sub-queries
    fusion_queries = state.get("fusion_queries", [state["question"]])
    if not fusion_queries:
        fusion_queries = [state["question"]]
        
    async def _search_query(q: str):
        return await asyncio.to_thread(master_retriever.search, query_text=q)

    all_results = await asyncio.gather(*[_search_query(q) for q in fusion_queries], return_exceptions=True)

    # Deduplicate results across all sub-queries
    unique_entities = set()
    top_entities: List[str] = []
    
    for res in all_results:
        if isinstance(res, Exception):
            log.warning("fusion_query_failed", error=str(res))
            continue
            
        for item in res.items:
            content = item.content if hasattr(item, "content") else str(item)
            if content not in unique_entities:
                unique_entities.add(content)
                top_entities.append(content)

    return {
        "reranked_entities": top_entities,
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "Agentic Mastermind",
            "status": "Selected optimal retrieval path (Hybrid Graph + Vector)",
            "timestamp": str(uuid.uuid4())
        }]
    }
