<div align="center">

# 🎙️ Worker Audio (Enterprise Audio Intelligence Pillar)

**Advanced GraphRAG Audio Processing, GDS Weaver & Sub-Second Retrieval**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Neo4j GDS](https://img.shields.io/badge/Neo4j-Graph_Data_Science-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 🎯 Overview

The `worker-audio` service is a high-performance intelligence pillar within OpenQ. It has evolved from a standard transcription service into a **Strategic GraphRAG engine**. It transcribes, diarizes, and semantic-links conversation turns into a persistent knowledge graph where relationships between speakers and topics are discovered autonomously using graph algorithms.

---

## 🚀 Key Features: The GraphRAG Advantage

### 1. GDS "Semantic Weaver" Pipeline
Post-indexing, the service triggers a **Neo4j Graph Data Science (GDS)** weaver:
- **Louvain Community Detection:** Automatically groups conversation segments into topical "Communities".
- **PageRank Centrality:** Ranks entities mentioned in the audio (people, companies) to determine their strategic importance in the discussion.
- **Hierarchical Summaries:** Generates LLM summaries of entire thematic blocks, enabling "Global RAG" answers.

### 2. Fast Retrieval Mode (⚡ Instant Response)
To respect compute costs and user time, the worker implements a **Skip-Indexing** logic:
- If a file is already processed, the worker detects the existing Neo4j graph nodes.
- It bypasses transcription and diarization entirely.
- It executes a **Hybrid Retriever** (Qdrant + Cypher) to answer the user's question in **< 1 second**.

---

## 🏗️ Architecture

### Indexing Flow (Heavy Lift)
1. **Profiler:** Validates audio constraints.
2. **Transcription (Gemini 2.5 Flash):** Native multimodal understanding of acoustic signals.
3. **Diarization:** Maps `SPEAKER_XX` to real names using LLM context.
4. **Entity Extraction:** Identifies critical terms via Llama 3.
5. **Graph Construction:** Builds the `(Speaker)-[:SPOKE]->(Turn)` topology in Neo4j.

### Retrieval Flow (High Speed)
1. **Text-to-Cypher:** Translates NL questions into graph traversal queries.
2. **Hybrid Search:** Combines Vector similarity from Qdrant with topological discovery from Neo4j.
3. **Community Context:** Uses `CommunitySummary` nodes to answer high-level "What was this meeting about?" questions efficiently.

---

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `LLM_MODEL_AUDIO` | Primary reasoning model (Gemini Flash). |
| `NEO4J_URI` | Connection to the Neo4j Graph DB with GDS enabled. |
| `QDRANT_URL` | Vector storage endpoint. |

---

## 🚀 Integration
| Task | Queue | Implementation |
|---|---|---|
| `app.worker.run_audio_analysis` | `pillar.audio` | `worker.py` |

*OpenQ Audio Intelligence: Where every word becomes a node in your strategy.*
