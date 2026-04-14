"""Nexus Router Agent — Intent Analysis."""
from typing import Dict, Any
import structlog
from app.infrastructure.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

async def nexus_router(state: NexusState) -> Dict[str, Any]:
    """Analyze query to determine the best path."""
    llm = get_llm(temperature=0, model_name="google/gemini-flash-1.5-8b")
    
    prompt = f"""You are the Multi-Pillar Intent Router for the Insightify Strategic Nexus.
    Your job is to classify the user question based on available documentation, code, and data sources.
    
    Question: {state['question']}
    Available Source IDs: {state['source_ids']}
    
    Context Summary (Sliding Window):
    {state.get('running_summary', 'Fresh dialogue.')}
    
    Routing Paths:
    - 'explore': Use this IF the question is about searching for links, finding relationships, or identifying how different things connect (e.g., 'What code uses this table?' or 'Find references to this product in Docs and Code').
    - 'direct_query': Use this IF the question is a direct factual inquiry about a specific pillar (e.g., 'What was the profit last month?' or 'Analyze the security of this function').
    
    Respond with ONLY one word: 'explore' or 'direct_query'."""
    
    res = await llm.ainvoke([SystemMessage(content=prompt)])
    decision = res.content.strip().lower()
    
    # Validation
    if "explore" in decision:
        path = "explore"
    else:
        path = "direct_query"
        
    logger.info("nexus_routing_decision", decision=path)
    return {"next_step": path}
