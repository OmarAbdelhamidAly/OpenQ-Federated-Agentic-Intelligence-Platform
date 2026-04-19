<div align="center">

# 📚 Worker PDF (DocRAG Multimodal Pillar)

**Research-Grade GraphRAG, Vision Decoding Matrix & Hybrid Retrieval**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Gemini 2.0](https://img.shields.io/badge/Gemini-2.0--Flash--Vision-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/)
[![Neo4j GDS](https://img.shields.io/badge/Neo4j-Graph_Data_Science-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Strategic_Orchestration-FF6B35)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 🎯 Overview

The `worker-pdf` service is the flagship document intelligence pillar of OpenQ. Unlike traditional extractors that treat PDFs as flat text, this service understands documents as **Spatial and Semantic Topologies**. It utilizes **Gemini 2.0 Flash Vision** to comprehend layouts natively and **Neo4j GraphRAG** to map relationships between extracted entities and document sections.

---

## 🏗️ Modern Architecture

The service is partitioned into two specialized specialized operational domains:

### 1. The Indexing Domain (`app/modules/pdf/agents/indexing/`)
- **Triple Synthesis Engine:**
  - **`deep_vision`**: Uses Vision LLMs to read charts, architecture flows, and complex tables natively.
  - **`fast_text`**: High-performance semantic partitioning for text-heavy documents.
  - **`hybrid_ocr`**: Blends traditional OCR with LLM-guided layout reconstruction.
- **Graph Knowledge Builder:** Automatically extracts strategic entities (People, Projects, Terms) and links them to specific `TextChunk` and `Page` nodes in Neo4j.
- **Semantic Weaver (GDS):** Executes Louvain Community Detection to cluster PDF sections into thematic modules.

### 2. The Retrieval Domain (`app/modules/pdf/agents/retrieval/`)
- **Hybrid Retrieval Matrix:** Executes parallel search across two tiers:
  - **Tier A (Vector):** High-recall search via Qdrant multi-vector embeddings.
  - **Tier B (Graph):** High-reasoning search via **Text-to-Cypher** traversal.
- **Community Summarization:** Answers global questions (e.g., "Summarize the financial strategy of this entire report") by querying `CommunitySummary` graph nodes instead of individual chunks.
- **Structural Analyst:** A specialized final node that synthesizes Vector + Graph context into a grounded, professional intelligence report.

---

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `LLM_MODEL_PDF` | Default intelligence model (Gemini 2.0 Flash recommended). |
| `NEO4J_URI` | Neo4j endpoint for GraphRAG storage. |
| `QDRANT_URL` | Vector DB endpoint for spatial chunk retrieval. |

---

## 🚀 Queues & Orchestration

| Task | Queue | Goal |
|---|---|---|
| `process_source_indexing` | `pillar.pdf` | Multimodal ingestion and GraphRAG construction. |
| `pillar_task` | `pillar.document` | Strategic Q&A and hybrid retrieval orchestration. |

*OpenQ PDF Intelligence: Vision to context, pixel to graph.*
