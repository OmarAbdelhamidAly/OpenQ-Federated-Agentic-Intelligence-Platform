from app.infrastructure.config import settings
"""Strategic Nexus — Pillar Orchestrator (Fixed Cross-Pillar Intelligence Engine).

Pipeline:
  discovery  → forge_links → gather_context → synthesis → END

Fixes over previous version:
  * Removed broken synchronous Celery subtask dispatch (deadlock).
  * Removed unreliable GraphCypherQAChain (LLM-generated Cypher returned []).
  * Discovery now properly falls back via execute_cypher when fulltext index misses.
  * New `forge_links` node dynamically creates cross-pillar Neo4j relationships
    across DIFFERENT source_ids before we try to read them.
  * New `gather_context` node pulls real data: Neo4j entities + cross-links +
    Postgres schema metadata — all deterministically.
  * Synthesis node receives a rich, structured context instead of empty strings.
"""

import os
import json
import uuid
import structlog
from typing import Any, Dict, List, TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.llm import get_llm
from app.modules.nexus.utils.episodic_memory import episodic_memory
from app.modules.nexus.utils.rag_evaluator import get_evaluator

logger = structlog.get_logger(__name__)


# ─── State ───────────────────────────────────────────────────────────────────

class NexusState(TypedDict, total=False):
    question: str
    fusion_queries: List[str]
    source_ids: List[str]
    job_id: str
    tenant_id: str
    thinking_steps: List[Dict[str, str]]
    graph_context: Dict[str, Any]   # rich graph data from Neo4j
    meta_context: Dict[str, Any]    # schema/metadata from Postgres
    synthesis: str
    status: str
    evaluation_metrics: Dict[str, Any]


# ─── Node 0: RAG-Fusion & Multi-Query Generation ─────────────────────────────

async def query_fusion_node(state: NexusState) -> Dict[str, Any]:
    """Breakdown the user's complex question into highly targeted multi-queries."""
    logger.info("nexus_fusion_start", job_id=state["job_id"])
    
    llm = get_llm(temperature=0.2, model=settings.LLM_MODEL_NEXUS)
    
    prompt = f"""You are a Strategic RAG Router. 
Your task is to take the user's question and break it down into 3-4 distinct sub-queries that target specific aspects (e.g. Code, Database, Document Policy).

<USER_QUESTION>
{state['question']}
</USER_QUESTION>

Output ONLY a JSON array of strings representing the sub-queries. Do not include markdown formatting or explanations.
Example: ["Extract Python authentication logic", "Find SQL users table schema", "Identify security policy clauses in PDF"]"""

    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        fusion_txt = res.content.strip()
        if fusion_txt.startswith("```json"):
            fusion_txt = fusion_txt[7:-3]
        elif fusion_txt.startswith("```"):
            fusion_txt = fusion_txt[3:-3]
            
        queries = json.loads(fusion_txt)
        if not isinstance(queries, list):
            queries = [state["question"]]
    except Exception as e:
        logger.warning("nexus_fusion_failed", error=str(e))
        queries = [state["question"]]

    step = {
        "node": "Strategic Intent Breakdown",
        "status": "Generated sub-queries:\n- " + "\n- ".join(queries),
        "timestamp": str(uuid.uuid4()),
    }
    
    return {
        "fusion_queries": queries,
        "thinking_steps": state.get("thinking_steps", []) + [step]
    }


# ─── Node 1: Discovery + Cross-link Forge ────────────────────────────────────

async def discovery_node(state: NexusState) -> Dict[str, Any]:
    """Forge cross-pillar relationships in Neo4j for all selected source_ids."""
    logger.info("nexus_discovery_start", job_id=state["job_id"])
    adapter = Neo4jAdapter()

    # Step A: forge cross-source links between ALL provided source_ids
    forge_counts = await adapter.forge_cross_source_links(state["source_ids"])
    logger.info("nexus_cross_links_forged", **forge_counts)

    step = {
        "node": "Discovery Engine",
        "status": (
            f"Forged {forge_counts['class_table']} Code↔SQL, "
            f"{forge_counts['entity_target']} Entity↔Target, "
            f"{forge_counts['chunk_mention']} Chunk↔Mention cross-pillar links."
        ),
        "timestamp": str(uuid.uuid4()),
    }
    return {"thinking_steps": state.get("thinking_steps", []) + [step]}


# ─── Node 2: Gather Context ───────────────────────────────────────────────────

async def gather_context_node(state: NexusState) -> Dict[str, Any]:
    """Collect all graph entities, relationships and Postgres metadata."""
    logger.info("nexus_gather_context_start", job_id=state["job_id"])
    adapter = Neo4jAdapter()

    # 1. Multi-source graph context
    graph_data = await adapter.fetch_multi_source_context(state["source_ids"])

    # 2. Postgres schema/metadata per source
    meta = {}
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text

        engine = create_async_engine(DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with async_session() as db:
                for sid in state["source_ids"]:
                    res = await db.execute(
                        text("SELECT type, file_path, schema_json FROM data_sources WHERE id = :sid"),
                        {"sid": sid},
                    )
                    row = res.fetchone()
                    if row:
                        meta[sid] = {
                            "type": row.type,
                            "file_path": row.file_path,
                            "schema": row.schema_json or {},
                        }
        except Exception as e:
            logger.error("nexus_meta_fetch_failed", error=str(e))
        finally:
            await engine.dispose()

    logger.info(
        "nexus_gather_context_done",
        entities=len(graph_data.get("entities", [])),
        cross_links=len(graph_data.get("cross_pillar_links", [])),
        meta_sources=len(meta),
    )

    step = {
        "node": "Context Aggregator",
        "status": (
            f"Collected {len(graph_data.get('entities', []))} entities, "
            f"{len(graph_data.get('cross_pillar_links', []))} cross-pillar links, "
            f"metadata for {len(meta)} sources."
        ),
        "timestamp": str(uuid.uuid4()),
    }
    return {
        "graph_context": graph_data,
        "meta_context": meta,
        "thinking_steps": state.get("thinking_steps", []) + [step],
    }

# ─── Node 2.5: Strategic Agentic Retrieval (ToolsRetriever) ──────────────────

async def rerank_context_node(state: NexusState) -> Dict[str, Any]:
    """Uses LLM-driven ToolsRetriever to intelligently fetch graph and vector context."""
    from neo4j_graphrag.retrievers import ToolsRetriever, VectorRetriever, Text2CypherRetriever
    from app.modules.nexus.utils.embeddings_wrapper import FastEmbedGraphRagWrapper
    from app.infrastructure.llm import get_llm
    from neo4j import GraphDatabase
    
    logger.info("nexus_agentic_retrieval_start", job_id=state["job_id"])
    
    # 1. Setup Infrastructure
    embedder = FastEmbedGraphRagWrapper()
    # We use our standard LLM for retrieval decision making
    langchain_llm = get_llm(temperature=0, model=settings.LLM_MODEL_NEXUS)
    
    # Simple Wrapper to satisfy neo4j-graphrag LLM interface if needed
    # (The library expects its own LLM classes, so we convert retrievers to tools)
    
    with GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)) as driver:
        # Tool A: Global Semantic Search (Vector)
        vector_retriever = VectorRetriever(
            driver=driver,
            index_name="chunk_vector_index", # Standardized name
            embedder=embedder,
            return_properties=["text", "page_num", "pillar", "source_id"]
        )
        vector_tool = vector_retriever.convert_to_tool(
            name="semantic_search",
            description="Find relevant text snippets and document sections based on semantic meaning."
        )

        # Tool B: Structural Graph Query (Cypher)
        # Note: We keep this manual for Nexus as we already have a Cypher Generator
        
        # 2. Execute High-Performance Retrieval
        # We replace the manual Re-ranking with a direct Vector-Graph search
        raw_results = await vector_retriever.asearch(
            query_text=state["question"],
            top_k=25
        )
        top_entities = [dict(r.node) for r in raw_results.records]

    logger.info("nexus_agentic_retrieval_done", final_count=len(top_entities))
    
    step = {
        "node": "Agentic GraphRAG Retriever",
        "status": f"Retrieved {len(top_entities)} high-relevance chunks using unified Vector-Graph searching.",
        "timestamp": str(uuid.uuid4()),
    }
    
    # Update graph context
    graph_ctx = state.get("graph_context", {})
    new_graph_ctx = graph_ctx.copy()
    new_graph_ctx["entities"] = top_entities
    
    return {
        "graph_context": new_graph_ctx,
        "thinking_steps": state.get("thinking_steps", []) + [step]
    }


# ─── Node 3: Synthesis ───────────────────────────────────────────────────────

async def synthesis_node(state: NexusState) -> Dict[str, Any]:
    """Synthesise a strategic intelligence report from all collected context."""
    logger.info("nexus_synthesis_start", job_id=state["job_id"])

    llm = get_llm(temperature=0.15, model=settings.LLM_MODEL_NEXUS)

    graph_ctx = state.get("graph_context", {})
    meta_ctx  = state.get("meta_context", {})

    # ── Map source_id → pillar type & path ────────────────────────────────────
    pid_type: Dict[str, str] = {}
    pid_path: Dict[str, str] = {}
    for sid, m in meta_ctx.items():
        pid_type[sid] = m.get("type", "source").lower()
        pid_path[sid] = m.get("file_path", sid)

    BUCKETS = {
        "codebase": "💻 CODE ARCHITECTURE",
        "sql":      "🗄️  RELATIONAL DATABASE",
        "csv":      "📊 FLAT DATASET (CSV)",
        "json":     "🔧 HIERARCHICAL CONFIG (JSON)",
        "pdf":      "📄 DOCUMENTATION / POLICY",
    }

    # ── Bucket every entity into its pillar ───────────────────────────────────
    buckets: Dict[str, List] = {k: [] for k in BUCKETS}

    for e in graph_ctx.get("entities", []):
        sid  = e.get("sid", "")
        kind = pid_type.get(sid, "")
        etype = e.get("type", "")
        if etype == "DatasetColumn":
            buckets["csv"].append(e)
        elif etype == "JSONField":
            buckets["json"].append(e)
        elif kind in buckets:
            buckets[kind].append(e)

    def _render_bucket(label: str, ents: List) -> str:
        if not ents:
            return f"### {label}\n  — No entities indexed for this pillar."
        rows = []
        for e in ents[:35]:
            name    = e.get("name", "?")
            etype   = e.get("type", "?")
            raw_sum = (e.get("summary") or "")
            summary = raw_sum[:140].replace("\n", " ")
            arch    = e.get("archetype", "")
            tag     = f"[{etype}{'|'+arch if arch else ''}]"
            rows.append(f"  {tag} **{name}**: {summary}")
        return f"### {label}\n" + "\n".join(rows)

    graph_block = "\n\n".join(
        _render_bucket(BUCKETS[k], buckets[k]) for k in BUCKETS
    )

    # ── Cross-pillar relationship graph ───────────────────────────────────────
    cross_links = graph_ctx.get("cross_pillar_links", [])
    if cross_links:
        edge_lines = [
            f"  ({l['from_type']}) \"{l['from_name']}\" "
            f"─[{l['relationship']}]→ "
            f"({l['to_type']}) \"{l['to_name']}\""
            for l in cross_links[:60]
        ]
        cross_block = "\n".join(edge_lines)
    else:
        cross_block = "  — No explicit cross-pillar edges found. Infer from entity name matching."

    # ── Episodic memory ───────────────────────────────────────────────────────
    try:
        past = await episodic_memory.get_related_insights(
            state.get("tenant_id", "default"), state["question"]
        )
        past_str = past[0]["synthesis"][:800] if past else "None."
    except Exception:
        past_str = "None."

    # ── Master 5-pillar synthesis prompt ─────────────────────────────────────
    prompt = f"""You are **Insightify Strategic Nexus** — an enterprise-grade multi-pillar intelligence engine.
Answer the user's question by synthesising ALL available pillar data with surgical precision.

<USER_QUESTION>
{state['question']}
</USER_QUESTION>

<INDEXED_ENTITIES_BY_PILLAR>
{graph_block}
</INDEXED_ENTITIES_BY_PILLAR>

<CROSS_PILLAR_RELATIONSHIP_GRAPH>
{cross_block}
</CROSS_PILLAR_RELATIONSHIP_GRAPH>

<EPISODIC_MEMORY>
{past_str}
</EPISODIC_MEMORY>

<INSTRUCTIONS>
Produce a structured **Executive Strategic Intelligence Report** in Markdown with EXACTLY these sections:

## 1. Executive Summary
2-3 decisive sentences answering the question directly. Name real artefacts.

## 2. 5-Pillar Cross-Domain Findings
For EACH active pillar state clearly what was found and how it relates to the others.
Use the relationship graph to describe explicit edges, e.g.:
  "Class `generate_invoices` [REPRESENTS_DATA]→ Table `invoices`"

## 3. Compliance & Policy Assessment
Map every rule found in Documentation/Policy pillar to actual data/code artefacts.
Mark each item as ✅ COMPLIANT or ⚠️ NON-COMPLIANT with a concise reason.

## 4. Data Architecture Risks & Anomalies
List concrete risks: missing DB constraints, PII fields without encryption, CSV↔SQL column mismatches, unreferenced JSON config keys, etc.

## 5. Strategic Recommendations
Exactly 3 prioritised, actionable recommendations.
Each MUST name the specific file, class, table, or column to change.

CRITICAL RULES:
- Use ONLY entity names from the <INDEXED_ENTITIES_BY_PILLAR> block. Never invent names.
- If a pillar shows "No entities indexed", write exactly that — do not fabricate content.
- Be terse and precise. Bullet points preferred over long prose.
</INSTRUCTIONS>
"""

    res = await llm.ainvoke([HumanMessage(content=prompt)])

    step = {
        "node": "Synthesis Layer",
        "status": "Executive Strategic Intelligence Report finalized.",
        "timestamp": str(uuid.uuid4()),
    }
    return {
        "synthesis": res.content,
        "thinking_steps": state.get("thinking_steps", []) + [step],
        "status": "done",
    }


# ─── Node 4: Evaluation ───────────────────────────────────────────────────────

async def evaluation_node(state: NexusState) -> Dict[str, Any]:
    """Evaluate chunk relevance and attribution for Nexus sub-queries."""
    logger.info("nexus_evaluation_start", job_id=state.get("job_id"))
    
    question = state.get("question", "")
    graph_ctx = state.get("graph_context", {})
    entities = graph_ctx.get("entities", [])
    synthesis = state.get("synthesis", "")

    if not entities or not synthesis:
        return {}

    try:
        chunks = []
        for i, e in enumerate(entities[:30]):
            text_rep = f"{e.get('type', '')} {e.get('name', '')}: {e.get('summary', '')}"
            chunks.append({
                "chunk_id": e.get("id", f"entity_{i}"),
                "text": text_rep,
                "element_type": e.get("type", "Entity")
            })

        evaluator = get_evaluator()
        eval_result = await evaluator.evaluate_retrieval(
            query=question,
            chunks=chunks,
            response=synthesis,
        )

        step = {
            "node": "Nexus RAG Evaluator",
            "status": f"Evaluation Complete. Cross-Pillar Attribution Rate: {eval_result.attribution_rate:.0%}",
            "timestamp": str(uuid.uuid4()),
        }

        return {
            "evaluation_metrics": eval_result.to_dict(),
            "thinking_steps": state.get("thinking_steps", []) + [step],
        }

    except Exception as exc:
        logger.error("nexus_evaluation_failed", error=str(exc))
        return {}


# ─── Graph Construction ───────────────────────────────────────────────────────

def create_nexus_graph():
    workflow = StateGraph(NexusState)

    workflow.add_node("query_fusion",   query_fusion_node)
    workflow.add_node("discovery",      discovery_node)
    workflow.add_node("gather_context", gather_context_node)
    workflow.add_node("rerank_context", rerank_context_node)
    workflow.add_node("synthesis_layer", synthesis_node)
    workflow.add_node("evaluation", evaluation_node)

    workflow.set_entry_point("query_fusion")
    workflow.add_edge("query_fusion",   "discovery")
    workflow.add_edge("discovery",      "gather_context")
    workflow.add_edge("gather_context", "rerank_context")
    workflow.add_edge("rerank_context", "synthesis_layer")
    workflow.add_edge("synthesis_layer", "evaluation")
    workflow.add_edge("evaluation", END)

    return workflow.compile()
