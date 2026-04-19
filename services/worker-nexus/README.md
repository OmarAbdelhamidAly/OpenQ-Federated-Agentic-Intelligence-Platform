<div align="center">

# 🌐 Worker Nexus (Federated Orchestrator Pillar)

**Multi-Pillar Strategic Aggregation & Cross-Ontology Graph Synthesis**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-6--Node%20Cycles-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Neo4j Master](https://img.shields.io/badge/Neo4j-Cross--Pillar%20Ontology-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)

</div>

---

## 🎯 Overview

The `worker-nexus` is the **Master Orchestrator** of the OpenQ platform. While specialized workers (Audio, Code, PDF, SQL) handle deep, intra-domain reasoning within their own GraphRAG schemas, Nexus operates at the **Inter-Domain Layer**. 

It is designed to solve complex, cross-functional strategic queries: 
> *"How does the technical architecture described in the PDF report correlate with the actual implementation in GitHub and the CEO's audio directives from the last meeting?"*

---

## 🏗️ Architecture: The Strategic Brain

Nexus executes a high-fidelity **Federated Orchestrator Graph**:

### 1. The Multi-Ontology Forge
Nexus queries the central Neo4j Knowledge Grid to link disparate entities from different pillars:
- **Audio ↔ Code:** Links a speaker in a call to a developer signature in a commit.
- **Document ↔ SQL:** Links a strategic project name in a PDF to a specific database schema entry.
- **Code ↔ Document:** Maps technical documentation sections to their living implementation.

### 2. Strategic Router & Explorer
The Nexus `router` analyzes the user's question and decides which specialized pillars need to be interrogated. It then coordinates the `explore` phase, fetching high-level `CommunitySummaries` from across the federation.

### 3. Cross-Domain Synthesis Engine
The `synthesis_engine` acts as the Chief Intelligence Officer. It takes the multi-pillar context blocks and generates a unified, high-density Strategic Intelligence Report that bridges the gap between raw data silos.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `LLM_MODEL_NEXUS` | Deepest reasoning model (e.g., Gemini 2.0 Pro or Flash). |
| `NEO4J_URI` | Access to the master cross-domain knowledge graph. |
| `REDIS_URL` | State management for the federated graph. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Goal |
|---|---|---|
| `nexus.discovery` | `pillar.nexus` | Invoked to reconcile new pillar nodes into the master ontology. |
| `pillar_task` | `pillar.nexus` | General cross-pillar intelligence execution. |

*OpenQ Nexus: Connecting the dots across your entire enterprise intelligence.*
