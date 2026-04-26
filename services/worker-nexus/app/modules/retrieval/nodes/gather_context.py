import uuid
import asyncio
import structlog
from typing import Any, Dict

from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

async def gather_context_node(state: NexusState) -> Dict[str, Any]:
    """Fetch data from Neo4j & Postgres in parallel to minimise latency."""
    log = logger.bind(job_id=state.get("job_id"), node="gather_context")

    adapter = Neo4jAdapter()
    source_ids = state.get("source_ids", [])

    async def fetch_postgres_meta() -> Dict[str, Any]:
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
