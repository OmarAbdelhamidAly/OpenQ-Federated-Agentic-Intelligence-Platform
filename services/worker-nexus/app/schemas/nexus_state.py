from typing import List, TypedDict, Dict, Any

class NexusState(TypedDict, total=False):
    question: str
    fusion_queries: List[str]
    source_ids: List[str]
    job_id: str
    tenant_id: str
    thinking_steps: List[Dict[str, str]]
    graph_context: Dict[str, Any]     # rich graph data from Neo4j
    meta_context: Dict[str, Any]      # schema/metadata from Postgres
    reranked_entities: List[str]       # top entities after agentic retrieval
    synthesis: str
    status: str
    evaluation_metrics: Dict[str, Any]
