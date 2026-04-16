<div align="center">

# 📊 Worker SQL (Relational Intelligence Pillar)

**Database Interrogation, HITL, and Hybrid Fusion Microservice**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-12--Node%20Cyclic-FF6B35)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 🎯 Overview

The `worker-sql` service is the flagship intelligence microservice for structured relational databases (MySQL, PostgreSQL, SQLite) within OpenQ. 

It handles autonomous schema discovery, mathematically accurate Text-to-SQL generation, secure database reading, and visualization synthesis. It stands out by implementing massive preventative mechanisms like **Human-in-the-Loop (HITL)** checkpoints and **Zero-Row Reflection** cycles.

---

## 🏗️ Architecture System & LangGraph Pipeline

This service maps unstructured thought across a complex 12-node Cyclic LangGraph StateGraph:

### Core Pipeline Lifecycle
1. **Data Discovery**: Uses the mapper logic to pull schemas, PKs/FKs, column types, limits, and low-cardinality enums for dynamic prompt building.
2. **Analysis Generator (Text-to-SQL)**: A ReAct agent queries the `insight_memory` database for previous "golden SQL" examples, generating precise ANSI SELECT statements and estimated execution plans.
3. **Execution & HITL Loop**: 
   - Operations flagged automatically, or via Tenant preference, as secure execute the SQL payload immediately. 
   - Protected databases trip the LangGraph `Interrupt`. The state is completely serialized to Redis via `AsyncRedisSaver`. The worker terminates successfully. Once an admin approves the SQL payload in via the API, the state is rehydrated and proceeds.
4. **Self-Healing Reflection**: If an explicit SQL Error is hit, or trivially if `0 Rows` are returned when rows were expected. The pipeline loops through a case-mismatch analyzer and alters queries logic to correct capitalization against existing `low_cardinality_values` up to 3 times before graceful failure.
5. **Hybrid Fusion**: On success, the JSON data array is merged with semantic context fetched from `Qdrant` (e.g. from PDF unstructured systems).
6. **Insight & Visualization**: Final graphs (ECharts/Plotly wrappers) are generated along with an executive-level executive summary.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Broker + LangGraph Checkpointing Database (`AsyncRedisSaver`). |
| `DATABASE_URL` | OpenQ metadata cluster. |
| `LLM_MODEL_SQL` | High-accuracy logic compiler model (`google/gemini-2.0-flash-001`). |
| `AES_KEY` | For decrypting the secure connection strings saved by the `api` module. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Role |
|---|---|---|
| `pillar_task` | `pillar.sql` / `.postgresql` / `.sqlite` | Starts or resumes SQL pipeline workflows. |
