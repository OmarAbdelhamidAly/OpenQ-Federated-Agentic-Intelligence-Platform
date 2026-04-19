from typing import Any, Dict, List, Optional
import operator
from typing_extensions import Annotated, TypedDict


class CodeAnalysisState(TypedDict):
    # ── Pipeline context ───────────────────────────────────────────────
    tenant_id: str
    user_id:   str
    source_id: str

    # ── Input ─────────────────────────────────────────────────────────
    question: str

    # ── Graph schema (populated by data_discovery_agent) ──────────────
    graph_schema: Optional[str]

    # ── Cypher generation (populated by cypher_generator_agent) ───────
    cypher_query:  Optional[str]
    cypher_params: Optional[Dict[str, Any]]

    # ── Query results (populated by cypher_execution_node) ───────────
    execution_results: Optional[List[Dict[str, Any]]]

    # ── Code snippets loaded on-demand from CodeStore ─────────────────
    # insight_agent populates this after fetching chunk_ids from results.
    code_snippets: Optional[List[Dict[str, str]]]  # [{"name": str, "code": str}]

    # ── Memory (Sliding Window & Summary) ─────────────────────────────
    chat_history:    Optional[List[Dict[str, str]]]
    running_summary: Optional[str]

    # ── Output ────────────────────────────────────────────────────────
    insight_report:    Optional[str]
    executive_summary: Optional[str]

    # ── Control flow ──────────────────────────────────────────────────
    error:              Optional[str]
    retry_count:        Annotated[int, operator.add]   # LangGraph auto-adds deltas
    reflection_context: Optional[str]

    # ── RAG Quality ───────────────────────────────────────────────────
    evaluation_metrics: Optional[Dict[str, Any]]
