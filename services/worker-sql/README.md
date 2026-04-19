<div align="center">

# 📊 Worker SQL (Relational Intelligence Pillar)

**Database Interrogation, HITL, Golden SQL Memory & Hybrid Context Fusion**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-12--Node%20Cyclic-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)

</div>

---

## 🎯 Overview

The `worker-sql` service is the structured intelligence engine of OpenQ. It transcends simple SQL generators by implementing a **Research-Grade Reasoning Loop** for relational databases (PostgreSQL, MySQL, SQLite). It handles schema discovery, "Golden SQL" memory retrieval, and Human-in-the-Loop (HITL) checkpoints to ensure absolute accuracy in enterprise environments.

---

## 🏗️ Architecture: The 12-Node Reasoning Graph

The service orchestrates complex analytical intents through an advanced StateGraph:

### 1. Schema Discovery & Context Injector
- Automatically inspects schemas, primary/foreign keys, and column types.
- **Enrichment:** Samples low-cardinality enums for dynamic prompt refinement, preventing case-sensitivity errors before they happen.

### 2. Analysis Generator (Advanced Text-to-SQL)
- **Golden SQL Memory:** Queries an internal vector store of successful previous queries to use as few-shot examples for the LLM.
- **Strategy Selection:** Decides whether to use `trend`, `comparison`, or `ranking` analytical patterns.

### 3. Execution, HITL & Persistence
- **State Persistence:** Uses `AsyncRedisSaver` to serialize the entire graph state.
- **Human-in-the-Loop:** Protected databases trigger a mandatory `Interrupt`. The worker waits for an administrator to approve the generated SQL via the API before proceeding.

### 4. Self-Healing & Hybrid Fusion
- **Reflection Loop:** If the query returns `0 Rows` or a `Syntax Error`, the **Reflection Agent** repairs the logic using database logs and low-cardinality metadata.
- **Hybrid Fusion:** Merges relational results with semantic insights from the **GraphRAG** pillars (PDF/Audio) to provide a unified business answer.

---

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `LLM_MODEL_SQL` | High-accuracy logic model (Gemini 2.0 Flash/Pro). |
| `AES_KEY` | For decrypting secure database connection strings. |
| `REDIS_URL` | Checkpointer and state storage for LangGraph. |

---

## 🚀 Queues & Resumption

| Task | Queue | Goal |
|---|---|---|
| `pillar_task` | `pillar.sql` | Start or resume (after HITL) SQL analytical workflows. |

*OpenQ SQL Intelligence: Relational precision at agentic scale.*
