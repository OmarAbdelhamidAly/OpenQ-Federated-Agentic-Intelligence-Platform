<div align="center">

# 📄 Worker JSON (Document Intelligence Pillar)

**NoSQL Aggregation, Semantic Nesting Decomposition & Hybrid RAG**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-Document%20Store-47A248?logo=mongodb&logoColor=white)](https://mongodb.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Semantic_RAG-018BFF?logo=qdrant&logoColor=white)](https://qdrant.tech)

</div>

---

## 🎯 Overview

The `worker-json` service is the NoSQL intelligence pillar of OpenQ. It is specifically designed to handle highly nested, semi-structured JSON log files and event streams. It bridges the gap between precise database filtering and conceptual semantic retrieval by implementing a **Dual-Tier RAG** architecture using MongoDB and Qdrant.

---

## 🏗️ Architecture: The 10-Node JSON Pipeline

The service utilizes a directed cyclic StateGraph to process complex document queries:

### 1. Semantic Decomposition
- **Flattening Engine:** Automatically decomposes excessively nested JSON objects and arrays into semantic clusters before ingestion.
- **Normalization:** Ensures consistency across disparate JSON schemas within the same collection.

### 2. Dual-Tier Search Strategy
Given a natural language query, the agent orchestrates two parallel actions:
- **Tier 1 (Exact):** Generates optimized **PyMongo Aggregation Pipelines** (`$match`, `$group`, `$facet`) to fetch exact numerical and categorical data from MongoDB.
- **Tier 2 (Fuzzy):** Hits **Qdrant Vector DB** for semantic similarity searches on text-rich event blobs or log descriptions.

### 3. Reflection & Synthesis
- **Aggregation Repair:** If a MongoDB pipeline fails or yields empty results, the **Reflection Agent** analyzes the schema and repairs the stage constraints.
- **Multi-Modal Insight:** Combines exact statistical data with semantic findings to generate a comprehensive business report.

---

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `MONGO_URI` | Connection to the MongoDB cluster. |
| `QDRANT_URL` | Vector database endpoint for JSON embeddings. |
| `LLM_MODEL_JSON` | Model used for aggregation pipeline generation. |

---

## 🚀 Queues & Tasks

| Task | Queue | Goal |
|---|---|---|
| `pillar_task` | `pillar.json` | Orchestrates the 10-node JSON reasoning graph. |

*OpenQ JSON Intelligence: Structured insights from semi-structured data.*
