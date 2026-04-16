<div align="center">

# 📄 Worker JSON (Document Intelligence Pillar)

**NoSQL Aggregation and Qdrant Semantic RAG Integration**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![MongoDB](https://img.shields.io/badge/MongoDB-Document%20Store-47A248?logo=mongodb&logoColor=white)](https://mongodb.com)

</div>

---

## 🎯 Overview

The `worker-json` service handles complex JSON log files and NoSQL document stores schemas within OpenQ. It excels in parsing highly nested event histories and flattening semantic arrays natively.

It seamlessly blends dual capabilities: exact boolean filtering powered by **MongoDB aggregations** and fuzzy conceptual matching powered by **Qdrant Vector Database** RAG embeddings (768d).

---

## 🏗️ Architecture Design

Operates on a **10-Node Directed Cyclic StateGraph**.

- **Semantic Decomposition**: Automatically flattens excessively nested JSON strings inside the document arrays before inserting them accurately into independent MongoDB collections.
- **Data Discovery & Guardrails**: Standard checks, isolating schema shapes safely without leaking PII variables downstream.
- **Analysis State**: Given a natural language query, it invokes dual-chain actions:
  - Drafting raw MongoDB PyMongo aggregation pipelines arrays `[{"$match": ...}, {"$group": ...}]`.
  - Hitting Qdrant for semantic similarity searches on vast text event blocks.
- **Reflection Check**: Error corrections on MongoDB Pipeline syntaxes.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Task dispatch cluster and async backend storage. |
| `DATABASE_URL` | Internal metadata system to transition job metrics. |
| `MONGO_URI` | The connection string mapping to the JSON document persistence instance. |
| `QDRANT_URL` | Trajectory to Vector Database deployment (default `http://qdrant:6333`). |
| `LLM_MODEL` | Standard processing model default parameters. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Details |
|---|---|---|
| `pillar_task` | `pillar.json` | JSON query job ID parameter mapping. |
