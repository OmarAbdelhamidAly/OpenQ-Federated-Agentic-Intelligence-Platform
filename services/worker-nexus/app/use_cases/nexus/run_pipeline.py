"""Entry point for the Strategic Nexus reasoning pipeline."""
import structlog
from typing import Any, Dict
from app.modules.nexus.agents.pillar_orchestrator import create_nexus_graph

logger = structlog.get_logger(__name__)

async def run_nexus_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the multi-pillar orchestration graph."""
    source_ids = payload.get("source_ids", [])
    question = payload.get("question", "")
    job_id = payload.get("job_id", "nexus-job")

    logger.info("nexus_pipeline_starting", job_id=job_id, source_ids=source_ids)

    # 1. Create the graph
    app = create_nexus_graph()

    # 2. Initial State
    initial_state = {
        "question": question,
        "source_ids": source_ids,
        "job_id": job_id,
        "tenant_id": payload.get("tenant_id", "default"),
        "thinking_steps": [],
        "graph_context": {},
        "meta_context": {},
        "synthesis": "",
        "status": "running",
    }

    # 3. Execute
    try:
        final_state = await app.ainvoke(initial_state)
        logger.info("nexus_pipeline_complete", job_id=job_id)
        return {
            "status": "done",
            "insight_report": final_state.get("synthesis", "No synthesis generated."),
            "thinking_steps": final_state.get("thinking_steps", [])
        }
    except Exception as e:
        logger.error("nexus_pipeline_failed", job_id=job_id, error=str(e))
        return {
            "status": "error",
            "error_message": str(e)
        }
