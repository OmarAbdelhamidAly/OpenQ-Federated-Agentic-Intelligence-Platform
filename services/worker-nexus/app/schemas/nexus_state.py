from typing import List, Annotated, TypedDict, Dict, Any, Optional
from operator import add

class NexusState(TypedDict):
    """LangGraph State for Universal Strategic Nexus."""
    source_ids: List[str]
    tenant_id: str
    question: str
    job_id: Optional[str]
    
    # ── Memory Layers ──────────────────────────────────────────
    chat_history: Annotated[List[Dict[str, str]], add]
    running_summary: str
    episodic_context: str
    procedural_instinct: str
    
    # Reasoning Trace
    discovery_logs: Annotated[List[str], add]
    pillar_responses: Annotated[List[Dict[str, Any]], add]
    
    # Final Output
    final_synthesis: str
    
    # Routing & Flow
    next_step: str
    status: str
    retry_count: int
