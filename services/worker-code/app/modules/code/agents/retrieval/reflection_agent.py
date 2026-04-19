import structlog
from app.domain.analysis.entities import CodeAnalysisState

logger = structlog.get_logger(__name__)


async def reflection_agent(state: CodeAnalysisState) -> dict:
    """
    Analyse a failed Cypher attempt and produce a correction hint.

    retry_count fix
    ---------------
    `CodeAnalysisState.retry_count` is declared as `Annotated[int, operator.add]`
    which means LangGraph *adds* any returned delta to the running total.
    Returning `1` here is correct and intentional — it increments the counter
    by exactly 1 each time the reflection node runs.

    The original `cypher_generator_agent` also returned `retry_count: 1` in
    its error branch, which caused a double-increment every failure cycle.
    That has been removed from the generator so the counter only increments
    here, in the dedicated reflection node.
    """
    error = state.get("error", "")
    query = state.get("cypher_query", "")
    source_id = state.get("source_id")

    logger.info(
        "cypher_reflection_started",
        source_id=source_id,
        retry_count=state.get("retry_count", 0),
        error=error,
    )

    reflection = (
        f"The previous Cypher query failed.\n\n"
        f"Query attempted:\n{query}\n\n"
        f"Error received:\n{error}\n\n"
        "Instructions for the next attempt:\n"
        "  1. Fix any syntax errors in the Cypher.\n"
        "  2. Return ONLY raw Cypher — no markdown fences.\n"
        "  3. Remember: nodes have NO `code` property; use `chunk_id`, "
        "`line_start`, `line_end` instead.\n"
        "  4. Always include WHERE n.source_id = $source_id.\n"
    )

    return {
        "reflection_context": reflection,
        "error":              None,   # clear error so routing picks up correctly
        "retry_count":        1,      # LangGraph operator.add → +1 to running total
    }
