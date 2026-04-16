<div align="center">

# 🌐 Worker Nexus (Federated Orchestrator Pillar)

**Multi-Pillar Strategic Aggregation and Knowledge Graph Synthesis**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-6--Node%20Cycles-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Neo4j Forge](https://img.shields.io/badge/Neo4j-Cross--Pillar%20Graph-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)

</div>

---

## 🎯 Overview

The `worker-nexus` module is the overarching brain of the OpenQ multi-agent system. While specialized workers (`worker-pdf`, `worker-sql`, etc.) interrogate isolated datasets, the Nexus worker interrogates them ALL simultaneously.

It acts as a Federated Multi-Pillar Orchestrator. When a user asks an executive query traversing multiple uploaded datasets ("How does our Q3 JSON ad-spend correlate with the SQL backend conversion pipeline and the CEO's audio transcript directives?"), it steps in to bridge the contextual logic gaps.

---

## 🏗️ Architecture Design

It executes a high-level **6-node Federated Orchestrator** StateGraph infrastructure.

### The Graph Pipeline (`modules/nexus/workflow.py`)
```
START → [router] →
    ├── explore        → [explorer] → [orchestrator]
    ├── direct_query   →              [orchestrator]
    └── finalize       →                             → [synthesizer]
                                                            ▼
                                                        [memory] → [save_cache] → END
```

### Synthesis Workflow 
1. **Neo4j Cross-Pillar Forge**: The `explorer` queries the central Neo4j Knowledge Grid to forge disparate relationships natively indexed by the specialized workers originally (`Code↔SQL`, `Entity↔Target`, `Chunk↔Mention`).
2. **Context Gatherer**: Collates all isolated facts into a mapped, tokenized memory store.
3. **5-Pillar Synthesis Engine**: `synthesis_engine` acts as the Chief Strategy LLM logic generator. Taking the 5-pillar context block, it outputs a highly dense, cross-domain Strategic Intelligence Report.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` / `DATABASE_URL` | State caching mechanisms and insight export arrays. |
| `LLM_MODEL_NEXUS` | The deepest reasoning model available (Default `google/gemini-2.0-flash-001`). |
| `NEO4J_URI` | Access endpoint to the enterprise master ontology mapping. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Invocation Parameter |
|---|---|---|
| `nexus.discovery` | `pillar.nexus` | Invoked automatically at end of ingestion periods for related schemas. |
| `pillar_task` | `pillar.nexus` | General intelligence execution requests via API router. |
