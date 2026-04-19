"""
Document Router Agent — Strategy-Aware Synthesis Mode Selection

Upgraded to be doc_strategy-aware: the router now reads the `doc_strategy`
field stored during indexing to select the correct synthesis engine,
ensuring the same strategy used during ingestion is used during retrieval.
"""
from app.infrastructure.config import settings
import structlog
from typing import Dict, Any, Literal
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

# Maps the indexing doc_strategy → analysis_mode for the workflow
_STRATEGY_TO_MODE = {
    "fast": "fast_text",
    "auto": "fast_text",      # auto defaults to fast unless hi_res was used
    "hi_res": "deep_vision",
    "ocr_only": "hybrid",
}

async def router_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Routes to direct chat or document analysis, and selects the synthesis engine.
    
    Decision 1: greeting vs query (intent classification)
    Decision 2: Which synthesis engine (fast_text | deep_vision | hybrid)
                   based on doc_strategy stored at indexing time.
    """
    question = state.get("question")
    source_type = state.get("source_type", "pdf")

    # ── Retrieve indexing strategy from source schema ──────────────────────────
    # doc_strategy is stored in schema_json during indexing
    schema_summary = state.get("schema_summary", {})
    doc_strategy = schema_summary.get("doc_strategy", "auto")

    # Map stored strategy to the correct synthesis engine
    analysis_mode = _STRATEGY_TO_MODE.get(doc_strategy, "fast_text")

    logger.info("router_agent_started",
                question=question[:60] if question else "",
                source_type=source_type,
                doc_strategy=doc_strategy,
                selected_mode=analysis_mode)

    # ── Intent Classification (fast model) ────────────────────────────────────
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_FAST)

    prompt = f"""You are a Smart Orchestrator for a Document AI system.
Analyze the user's message and categorize it as one of:

1. 'greeting': Simple hellos, thank yous, or small talk unrelated to documents.
2. 'query': Questions that require searching document content.

USER MESSAGE: {question}

Output ONLY THE CATEGORY NAME ('greeting' or 'query')."""

    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        category = res.content.strip().lower()

        if "greeting" in category:
            logger.info("router_decision", route="greeting")
            return {
                "route": "greeting",
                "analysis_mode": analysis_mode,
                "doc_strategy": doc_strategy,
            }

        logger.info("router_decision", route="query", mode=analysis_mode)
        return {
            "route": "query",
            "analysis_mode": analysis_mode,
            "doc_strategy": doc_strategy,
        }

    except Exception as e:
        logger.error("router_failed", error=str(e))
        # Fail-safe: default to fast_text query
        return {
            "route": "query",
            "analysis_mode": analysis_mode,
            "doc_strategy": doc_strategy,
        }
