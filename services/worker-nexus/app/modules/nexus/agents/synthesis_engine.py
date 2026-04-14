"""Nexus Synthesis Engine Agent — Final Intelligence Synthesis."""
from typing import Dict, Any
import structlog
from app.infrastructure.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

async def synthesis_engine(state: NexusState) -> Dict[str, Any]:
    """Combine discovery logs and pillar responses into a final report."""
    llm = get_llm()
    
    # Format discovery traces
    discovery_text = "\n".join(state.get("discovery_logs", []))
    
    # Format specialist outputs
    specialist_texts = "\n\n".join([f"### Specialist ({r['type']}):\n{r['content']}" for r in state.get("pillar_responses", [])])
    
    prompt = f"""You are the Grand Strategist for Insightify.
    Synthesize all cross-pillar signals into a single, high-impact Strategic Intelligence Report.
    
    Question: {state['question']}
    
    Discovery Trace (Knowledge Graph Relationships):
    {discovery_text}
    
    Specialist Intelligence (Raw Pillar Outputs):
    {specialist_texts}
    
    Report Structure:
    1. Executive Summary (Synthesized Answer)
    2. Cross-Source Intelligence (How the sources connect)
    3. Strategic Recommendations
    
    Respond in markdown format."""
    
    res = await llm.ainvoke([SystemMessage(content=prompt)])
    final_report = res.content
    
    logger.info("nexus_synthesis_complete", report_length=len(final_report))
    return {"final_synthesis": final_report}
