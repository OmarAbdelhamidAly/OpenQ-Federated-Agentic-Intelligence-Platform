import structlog
from app.domain.analysis.entities import CodeAnalysisState

logger = structlog.get_logger(__name__)


async def output_assembler(state: CodeAnalysisState) -> dict:
    """Package the final analysis payload for the Celery task caller."""
    logger.info("output_assembler_started", source_id=state.get("source_id"))

    return {
        "insight_report":     state.get("insight_report"),
        "executive_summary":  state.get("executive_summary"),
        "graph_schema":       state.get("graph_schema"),
        "cypher_query":       state.get("cypher_query"),
        "execution_results":  state.get("execution_results"),
        "code_snippets":      state.get("code_snippets"),
        "evaluation_metrics": state.get("evaluation_metrics"),
        "error":              state.get("error"),
    }
