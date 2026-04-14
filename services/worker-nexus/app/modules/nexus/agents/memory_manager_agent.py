"""Memory Manager Agent for Nexus — Handles dialogue compression and sliding window."""
import structlog
from typing import Dict, Any
from app.infrastructure.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

MAX_HISTORY = 4 # Keep last 4 turns for immediate context

async def memory_manager_agent(state: NexusState) -> Dict[str, Any]:
    """Compress chat history into a running summary if it exceeds the limit."""
    history = state.get("chat_history", [])
    current_summary = state.get("running_summary", "")
    
    if len(history) <= MAX_HISTORY:
        return {} # No compression needed yet
        
    logger.info("nexus_memory_compression_started", history_len=len(history))
    
    # We use a fast model for summarization
    llm = get_llm(temperature=0, model_name="google/gemini-flash-1.5-8b")
    
    prompt = f"""You are the Memory Manager for the Strategic Nexus.
    Your job is to update the 'Running Summary' of the strategic dialogue to preserve key insights without losing the big picture.
    
    Current Summary: {current_summary}
    Recent Dialogue: {history[-MAX_HISTORY:]}
    
    Update the summary to include any new strategic findings, pillar correlations, or critical user requests.
    Keep it concise but technical. Focus on relationships discovered in the graph or pillar outcomes."""
    
    res = await llm.ainvoke([SystemMessage(content=prompt)])
    new_summary = res.content
    
    # Keep only the tail of the history
    truncated_history = history[-MAX_HISTORY:]
    
    logger.info("nexus_memory_compression_complete")
    return {
        "chat_history": truncated_history,
        "running_summary": new_summary
    }
