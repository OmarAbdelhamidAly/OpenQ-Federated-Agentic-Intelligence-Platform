import structlog
from app.domain.analysis.entities import CodeAnalysisState
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)


async def data_discovery_agent(state: CodeAnalysisState) -> dict:
    """
    Build a rich graph schema description for the Cypher generator.

    Improvement over the original
    ------------------------------
    The previous implementation returned a hardcoded static string that
    described the schema but gave the LLM no information about the actual
    size of the codebase being interrogated.  With no sense of scale the
    model cannot make good decisions (e.g. adding LIMIT clauses, choosing
    between MATCH patterns, etc.).

    This version queries Neo4j for live per-label node counts and injects
    them into the schema string so the LLM has accurate context:

        Codebase stats: 1,234 Files | 89 Directories | 2,341 Functions | 456 Classes

    Schema is still deterministic (not LLM-generated), so it cannot
    hallucinate node labels or property names.
    """
    source_id = state.get("source_id")
    logger.info("code_data_discovery_started", source_id=source_id)

    # ── Live node-count stats from Neo4j ─────────────────────────────
    try:
        adapter = Neo4jAdapter()
        stats   = await adapter.get_schema_stats(source_id)
    except Exception as exc:
        logger.warning("code_discovery_stats_failed", error=str(exc))
        stats = {}

    def _fmt(label: str) -> str:
        count = stats.get(label, 0)
        return f"{count:,} {label}{'s' if count != 1 else ''}"

    stats_line = (
        f"Codebase stats: {_fmt('File')} | {_fmt('Directory')} | "
        f"{_fmt('Function')} | {_fmt('Class')}"
    )

    schema = (
        f"{stats_line}\n\n"
        "Node labels and their properties:\n"
        "  (Directory {source_id, path, name})\n"
        "  (File      {source_id, path, name, extension})\n"
        "  (Class     {source_id, file_path, name, chunk_id, line_start, line_end})\n"
        "  (Function  {source_id, file_path, name, chunk_id, line_start, line_end})\n\n"
        "Relationships:\n"
        "  (Directory)-[:CONTAINS]->(Directory)\n"
        "  (Directory)-[:CONTAINS]->(File)\n"
        "  (File)-[:DEFINES]->(Class)\n"
        "  (File)-[:DEFINES]->(Function)\n\n"
        "Important notes for query generation:\n"
        "  - ALWAYS filter by source_id using the $source_id parameter.\n"
        "  - 'code' is NOT a property on Class/Function nodes. Use chunk_id to reference code.\n"
        "  - Use line_start / line_end to report where an entity is defined.\n"
        "  - For fuzzy name search use: WHERE n.name CONTAINS 'keyword'\n"
        "  - Full-text search (with relevance scoring):\n"
        "    CALL db.index.fulltext.queryNodes('codeEntityNames', 'keyword~1 OR keyword*')\n"
        "    YIELD node AS n, score WHERE n.source_id = $source_id\n"
        "    RETURN n.name, n.file_path ORDER BY score DESC\n"
    )

    return {"graph_schema": schema, "error": None}
