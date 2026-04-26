import uuid
import asyncio
import structlog
from typing import Any, Dict

from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.generation.prompts import RagTemplate
from neo4j_graphrag.memory import Neo4jMessageHistory

from app.infrastructure.config import settings
from app.schemas.nexus_state import NexusState
from app.modules.retrieval.dependencies import get_neo4j_driver, get_rate_limiter

logger = structlog.get_logger(__name__)

async def synthesis_node(state: NexusState) -> Dict[str, Any]:
    """Generate the final intelligence report with persistent Neo4j memory."""
    log = logger.bind(job_id=state.get("job_id"), node="synthesis")

    neo4j_driver = get_neo4j_driver()
    rate_limiter = get_rate_limiter()

    graphrag_llm = OpenAILLM(
        model_name=settings.LLM_MODEL_NEXUS,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        rate_limit_handler=rate_limiter,
    )

    # Persistent conversation memory stored in Neo4j (Auditability)
    session_id = f"{state.get('tenant_id', 'global')}_{state.get('job_id')}"
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
