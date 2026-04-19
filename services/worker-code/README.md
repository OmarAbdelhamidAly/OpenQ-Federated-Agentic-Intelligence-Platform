<div align="center">

# 🧑‍💻 Worker Code (Codebase Intelligence Pillar)

**Advanced GDS GraphRAG, Abstract Syntax Tree Parsing & Architectural Logic**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Neo4j GDS](https://img.shields.io/badge/Neo4j-Graph_Data_Science-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![Tree-sitter](https://img.shields.io/badge/AST-Tree--sitter-black)](https://tree-sitter.github.io/tree-sitter/)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-Cyclic%20StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 🎯 Overview

The `worker-code` service is the structural intelligence core of OpenQ. It utilizes a **Research-Grade GraphRAG** architecture to transform repositories from flat files into a multi-dimensional knowledge graph. By parsing Abstract Syntax Trees (ASTs) and applying Graph Data Science, it enables deep structural reasoning that traditional vector-based RAG cannot achieve.

---

## 🏗️ Architecture: The GDS Core

### 1. The Ingestion Pipeline (AST to Graph)
- **Universal Parsing:** Uses Tree-sitter to support 11+ languages, extracting classes, functions, and their call dependencies.
- **Semantic Weaver (GDS):** After the base graph is built, the service runs a native Neo4j GDS pipeline:
  - **Louvain Modularity:** Groups functions and classes into **Architectural Modules**, autonomously discovering the project's internal structure.
  - **PageRank Centrality:** Calculates the `architectural_importance` of every node, identifying the "Logical Heart" of the codebase.

### 2. The Retrieval Matrix (GDS-Aware Q&A)
- **Text-to-Cypher:** Generates complex graph queries that go beyond text matching.
- **Centrality-Ranked Answers:** When asked about "core logic," the retriever prioritizes nodes with high PageRank scores.
- **Module-Level Reasoning:** Can answer questions about entire code modules by querying the `CommunitySummary` summaries generated during clustering.
- **The Self-Healing Loop:** Implements a ReAct-style reflection agent that repairs failed Cypher queries up to 3 times.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `NEO4J_URI` | Bolt endpoint to Neo4j (Requires GDS plugin). |
| `LLM_MODEL_CODE` | Large context model for complex Cypher generation. |
| `REDIS_URL` | Task broker for repository ingestion. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Goal |
|---|---|---|
| `process_codebase_indexing` | `pillar.code` | Full repository ingestion and GDS weaving. |
| `pillar_task` | `pillar.codebase` | Codebase Q&A and architectural analysis. |

*OpenQ Code Intelligence: Mapping the DNA of your software.*
