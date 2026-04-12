from app.infrastructure.config import settings
import structlog
from typing import Dict, Any, Literal
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

async def router_agent(state: AnalysisState) -> Dict[str, Any]:
    """Decides if the message is a greeting or a document query, and selects retrieval mode."""
    question = state.get("question")
    source_type = state.get("source_type", "pdf")
    
    # We use a very fast model for routing
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_FAST)
    
    prompt = f"""You are a Smart Orchestrator for a PDF AI system. Analyze the user's message and categorize it.
    
    CATEGORIES:
    1. 'greeting': Simple hellos, thank yous, or small talk.
    2. 'query': Questions that require searching the document (e.g. "What is the total profit?", "Show me the chart").
    
    USER MESSAGE: {question}
    
    Output ONLY THE CATEGORY NAME ('greeting' or 'query')."""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        category = res.content.strip().lower()
        
        if "greeting" in category:
            return {"route": "greeting"}
            
        # If it's a query, we need to decide the mode based on available tools.
        # For now, we default to the "smartest" mode requested by the user during indexing,
        # but in a future iteration, we can let the LLM pick between fast_text/hybrid/vision.
        return {"route": "query"}
        
    except Exception as e:
        logger.error("router_failed", error=str(e))
        return {"route": "query"} # Default to search
