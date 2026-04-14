import os
import redis.asyncio as redis
from langgraph.checkpoint.redis import AsyncRedisSaver
import structlog
from app.modules.code.workflow import build_code_workflow

logger = structlog.get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Note: worker-code creates its own redis connection pool
redis_connection = redis.from_url(REDIS_URL)

_workflow_instance = None

def get_pipeline():
    global _workflow_instance
    if _workflow_instance is None:
        checkpointer = AsyncRedisSaver(redis_connection)
        _workflow_instance = build_code_workflow(checkpointer=checkpointer)
    return _workflow_instance

async def run_codebase_pipeline(question: str, source_id: str, tenant_id: str, session_id: str = None) -> dict:
    """Executes the Text2Cypher LangGraph workflow."""
    logger.info("codebase_pipeline_started", question=question, source_id=source_id, session_id=session_id)
    pipeline = get_pipeline()
    
    initial_state = {
        "tenant_id": tenant_id,
        "user_id": "system",
        "source_id": source_id,
        "question": question,
        "retry_count": 0
    }
    
    import uuid
    # Use the session_id to maintain conversation history in Redis
    thread_id = session_id if session_id else f"codebase_{source_id}_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        final_state = await pipeline.ainvoke(initial_state, config)
        logger.info("codebase_pipeline_finished", source_id=source_id)
        
        return {
            "insight_report": final_state.get("insight_report"),
            "executive_summary": final_state.get("executive_summary"),
            "chart_json": None, # Codebases don't typically have charts
            "cypher_query": final_state.get("cypher_query"),
            "results": final_state.get("execution_results")
        }
    except Exception as e:
        logger.error("codebase_pipeline_failed", error=str(e))
        return {
            "insight_report": f"Pipeline failed: {str(e)}",
            "executive_summary": "Error analyzing codebase.",
            "error": str(e)
        }
