<div align="center">

# 🧑‍💻 Worker Code (Codebase Intelligence Pillar)

**Advanced Graph-RAG Document & Codebase Analysis Microservice**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Neo4j Graph](https://img.shields.io/badge/Neo4j-Knowledge%20Graph-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-Cyclic%20StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 🎯 Overview

The `worker-code` service is a specialized intelligence microservice within the OpenQ platform dedicated to profound codebase analysis. It implements an advanced **Graph-RAG (Retrieval-Augmented Generation)** architecture tailored exclusively for structural source code comprehension.

Unlike traditional analyzers that treat code as flat text and blindly dump it into a Vector Database, `worker-code` parses repositories using compiler-grade Abstract Syntax Trees (ASTs), maps deep structural dependencies into a **Neo4j Graph Database**, offloads raw code blobs to lightweight storage, and leverages a LangGraph-orchestrated **Text-to-Cypher pipeline** for zero-hallucination insights.

---

## 🏗️ Architecture Deep Dive: Graph RAG and Semantic Indexing

This worker operates in two primary phases asynchronously managed by **Celery**:

### 1. The Indexing Phase (Ingestion Pipeline)

When a new codebase is connected, the entire ingestion flow is orchestrated by `app/use_cases/ingestion/service.py` via the Celery task `process_codebase_indexing`.

#### 1.1 Extraction and Sanitization
The system begins by interacting with the `CodeExtractor`. 
- Repositories are cloned from GitHub into a temporary directory (respecting branches and private access tokens).
- Before actual ingestion, `Neo4jAdapter.delete_source_graph()` and `CodeStore.delete_all()` are called to completely wipe out any stale data for that specific tenant/Data Source ID to prevent duplication or ghost data.

#### 1.2 Universal AST Parsing (`ast_parser.py`)
Code parsing is handled by **Tree-sitter**, a compiler-grade incremental parsing library.
- The `ASTParser` class natively understands 11 languages (Python, JavaScript/TypeScript, Java, C++, Go, Rust, Ruby, PHP, C#, HTML, and CSS).
- As it traverses the files, it identifies fundamental building blocks: `Class`, `Function` / `Method`, `Import` statements, and `Call` expressions.
- It extracts precise metadata, including the `line_start` and `line_end` of each block.

#### 1.3 Lightweight Blob Storage (`code_store.py`)
This is a critical system design optimization. Storing multi-kilobyte text blobs of raw code directly as string properties inside Neo4j severely impairs database performance and RAM utilization during traversal queries.
- Raw code is immediately hashed using SHA-256 mathematically tied to `(source_id, entity_type, name)`. This ensures idempotency.
- The `CodeStore` drops this raw text block directly into a persistent volume on the file system (`/data/code_chunks`) as a tiny `.txt` file named after the hash (`chunk_id`).
- Neo4j only receives the lightweight 16-character `chunk_id`.

#### 1.4 Concurrent Semantic Enrichment (`enricher.py`)
To enable AI comprehension, raw code syntax isn't enough.
- The `CodeEnricher` takes the parsed functions/classes and sends them via asynchronous queues to an LLM (typically via OpenRouter).
- It generates a human-readable `summary` of the logic.
- It generates a 768-dimensional mathematical `embedding` (vector format) of that summary.
- This happens concurrently in batches (e.g., 10 at a time) to dramatically speed up ingestion times.

#### 1.5 Graph Construction (`neo4j_adapter.py`)
Finally, the `Neo4jAdapter` constructs the actual topology using Cypher `UNWIND` and `MERGE` operators for high-throughput batch writes.
- **Hierarchical Nodes**: `Directory` → `[:CONTAINS]` → `File`.
- **Entity Nodes**: `File` → `[:DEFINES]` → `Class` / `Function`.
- **Dependency Edges**: `File` → `[:DEPENDS_ON]` → `File` (based on import statements).
- **Execution Edges**: `Function` / `Class` → `[:CALLS]` → `Function` (capturing the call stack).

**Crucially, Indexing explicitly provisions:**
- Full-text indexes over names and summaries (`db.index.fulltext.queryNodes`).
- Vector indexes over embeddings for cosine similarity lookups.

*At the end of ingestion, structural and vector indices are automatically created, and the service triggers a `nexus.discovery` task for cross-pillar federation.*

---

### 2. The Retrieval Phase (Q&A Execution)

When a question is asked (e.g., "Where is the authentication middleware located?"), the Celery `pillar_task` spins up the LangGraph state machine located in `app/modules/code/workflow.py`.

#### 2.1 Context Discovery (`data_discovery_agent.py`)
The pipeline does not blindly guess table shapes. The Discovery Agent queries Neo4j to count the relative frequency of labels (`Class`, `Function`, `File`). This provides the generator LLM with a structural understanding of the repository's scale.

#### 2.2 ReAct Text-to-Cypher (`cypher_generator_agent.py`)
An intentionally localized, specialized LLM is provided with the user's intent and prompt instructions.
- The Prompt strictly instructs the model to use `chunk_id` for reference and never hallucinate raw code properties.
- It utilizes the Full-text indices configured during Ingestion: e.g. `CALL db.index.fulltext... YIELD node AS n`.

#### 2.3 The Self-Healing Execution Loop (`cypher_execution_node` & `reflection_agent.py`)
Cypher is highly prone to syntax errors and case-sensitivity issues on zero-shot runs.
- `cypher_execution_node` pings Neo4j.
- **Failures & Empty Drops:** If Neo4j throws a syntax error, or if the `row_count == 0` (meaning the LLM hallucinated a node name), the `route_after_execution` conditional edge intercepts the failure.
- The state is passed to the `reflection_agent.py`. This Node acts purely as a "Surgeon". It assesses the Neo4j error alongside the original Cypher script and repairs it. It then loops explicitly back to Execution (skipping Generation to preserve intent). It will attempt this up to 3 times before graceful failure.

#### 2.4 Insight Synthesis & Blob Hydration (`insight_agent.py`)
When the Cypher query successfully returns rows from Neo4j, those rows contain the graph relationships and structural metadata—but only the `chunk_id`, not the actual code.
- The system intercepts the Cypher payload.
- It triggers `CodeStore.load_many()`, passing down the resulting `chunk_ids`.
- The `CodeStore` reads the disk-based `.txt` files containing the raw text up to a strict token ceiling context limit (e.g., `max_chars = 3000`).
- The `insight_agent.py` receives the final prompt bridging the semantic reality: "You see this graph relationship, and here is the literal codebase text." The agent drafts grounded, hallucination-resistant answers. 

#### 2.5 Delivery & Checkpointing
The `memory_manager_agent` compresses the transaction context into a slide-window summary. The `output_assembler` bundles the Cypher code, chart payloads, and the final textual insight into the resulting payload and returns it seamlessly bridging graph infrastructure securely to the UI workspace.

---

## ⚙️ Environment Configuration

Ensure the following configuration variables are populated in your `.env`:

| Variable | Description |
|---|---|
| `REDIS_URL` | Redis instance for the Celery message broker and backend. |
| `DATABASE_URL` | PostgreSQL URL for fetching and updating Analysis Job statuses asynchronously. |
| `NEO4J_URI` | Bolt connector string to the Neo4j Graph DB deployment (`bolt://...:7687`). |
| `NEO4J_USERNAME` | Master user for the database (default: `neo4j`). |
| `NEO4J_PASSWORD` | Password for Graph DB authentication. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Payload |
|---|---|---|
| `process_codebase_indexing` | `pillar.code` | `{ "source_id": "<uuid>" }` |
| `pillar_task` | `pillar.codebase` | `{ "job_id": "<uuid>" }` |

When a task executes effectively, it parses state metrics back into the main PostgreSQL `analysis_jobs` and `analysis_results` records, enabling synchronous UI updates on the Frontend without locking up primary API resources.
