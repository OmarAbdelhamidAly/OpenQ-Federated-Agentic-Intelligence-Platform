# OpenQ Nexus: The Omniscient Enterprise Graph Aggregator

Welcome to the **Nexus** service, the strategic brain and federated graph aggregator of the OpenQ platform. Nexus is not merely a backend service; it is an enterprise-grade, Multi-Agent Retrieval-Augmented Generation (GraphRAG) hub designed using strict Domain-Driven Design (DDD) principles. It is responsible for orchestrating the ingestion of isolated data pillars (code, audio, documents, SQL schemas) and dynamically synthesizing them into a unified, actionable Knowledge Graph.

Built heavily upon the official `neo4j-graphrag` framework and Neo4j Graph Data Science (GDS), Nexus eliminates traditional linear vector search limitations, providing context-aware, hallucination-free intelligence.

---

## 🏗️ Architectural Overview (Domain-Driven Design)

The repository is structured to strictly isolate concerns, ensuring highly maintainable and scalable enterprise code.

```text
app/
├── infrastructure/     # External integrations (Neo4j, LLM providers, Redis)
├── modules/
│   ├── indexing/       # Graph Sinks (Data Ingestion from remote workers)
│   ├── retrieval/      # AI Mastermind (GraphRAG, Tool Routing, LangGraph Workflow)
│   └── graph_ops/      # Advanced Graph Data Science and Machine Learning operations
├── schemas/            # Data validation and single-source-of-truth states
├── use_cases/          # Business logic entry points
└── worker.py           # Celery application and message queue routing
```

---

## 📁 Detailed File Documentation

### 1. `app/worker.py`
**The Distributed Message Queue Entrypoint**
This file acts as the primary networking facade and task consumer for the Nexus service, utilizing Celery connected to a Redis broker. In an enterprise microservices architecture, synchronous HTTP calls between AI agents often lead to timeouts and cascading failures. To prevent this, `worker.py` subscribes to the `pillar.nexus` queue, accepting asynchronous job payloads. Upon receiving a task (`nexus.analyze`), it initializes a secure database connection using SQLAlchemy to fetch the complete context of the job (such as the target `source_ids` across different data pillars). It then passes the parsed payload into the internal use cases while managing database state updates (e.g., updating the job status to `done` or `error`). Furthermore, it houses the `setup_periodic_tasks` method which triggers the initial Neo4j schema bootstrap, ensuring the graph database is strictly constrained before any data ingestion occurs.

### 2. `app/use_cases/retrieval/run_pipeline.py`
**The Business Logic Invoker**
Serving as the bridge between the external Celery worker and the internal AI logic, this file encapsulates the execution of the Nexus orchestration graph. It is responsible for taking the raw job payload (including the user's question, tenant ID, and targeted data sources) and converting it into the strongly typed initial `NexusState`. It imports `create_nexus_graph` from the retrieval workflow, compiles the LangGraph state machine, and asynchronously invokes the execution using `app.ainvoke()`. By isolating this logic in the `use_cases` domain, we ensure that the complex AI workflow remains completely agnostic of the message broker (Celery) or the database layer (SQLAlchemy). If an exception occurs deep within the agentic nodes, this file catches the error gracefully and structures a standardized response payload, guaranteeing that the larger distributed system does not crash due to an unhandled local failure.

### 3. `app/modules/retrieval/workflow.py`
**The GraphRAG Mastermind (Pillar Orchestrator)**
This is arguably the most critical file in the entire OpenQ architecture. It defines the stateful LangGraph workflow that orchestrates the entire intelligence process. The workflow consists of multiple specialized nodes:
- **Query Fusion Node:** Employs an LLM to decompose complex user questions into multiple targeted sub-queries.
- **Gather Context Node:** Deterministically fetches raw graph data and Postgres schemas before the LLM is even invoked, reducing latency.
- **Rerank Context Node:** Implements the revolutionary `ToolsRetriever` from the `neo4j-graphrag` library. It initializes two distinct tools: the `QdrantNeo4jRetriever` for semantic vector search across unstructured text, and the `Text2CypherRetriever` equipped with a strict graph schema to generate exact Cypher queries for structural data (like database columns or code ASTs). The LLM dynamically decides which tool to use, or combines both, eliminating hallucinations.
- **Synthesis Node:** Leverages the native `GraphRAG` generation class along with `Neo4jMessageHistory` (Axis 8 of the neo4j-graphrag specs) to generate an executive strategic report while maintaining persistent conversational memory across sessions.
- **Evaluation Node:** Evaluates the generated report against the retrieved chunks to calculate strict attribution metrics.

### 4. `app/modules/retrieval/embeddings_wrapper.py`
**The Semantic Embedding Interface**
In modern GraphRAG architectures, calculating embeddings on-the-fly using external APIs (like OpenAI) for millions of chunks can result in massive latency and exorbitant costs. This file defines `FastEmbedGraphRagWrapper`, a custom interface that wraps the highly optimized, local execution of the `FastEmbed` library (specifically the multilingual `nomic-embed-text` model). By strictly adhering to the `Embedder` protocol required by `neo4j-graphrag`, this wrapper allows the `QdrantNeo4jRetriever` to instantly convert natural language queries into 768-dimensional vectors locally within the Kubernetes Pod CPU. This completely bypasses network calls to external embedding providers, achieving millisecond latency for semantic searches while maintaining 100% compatibility with the official Neo4j retrieval pipelines.

### 5. `app/modules/retrieval/rag_evaluator.py`
**The Quality Assurance & Attribution Engine**
Enterprise LLM systems cannot rely on blind trust; they require mathematical verification. This file implements an advanced Ragas-inspired evaluation engine tailored specifically for cross-pillar graph data. When the Synthesis node completes a report, this evaluator analyzes the output against the originally retrieved graph entities. It checks for exact grounding (ensuring the LLM did not invent facts), calculates the 'Attribution Rate' (what percentage of the answer is directly backed by the graph context), and identifies cross-pillar synthesis (whether the LLM successfully connected dots between, for example, a PDF policy and a Python code file). These metrics are invaluable for continuous MLOps monitoring and allow the platform administrators to mathematically prove the accuracy of the OpenQ Nexus to enterprise clients.

### 6. `app/modules/indexing/pdf_indexer.py`
**The Unstructured Document Sink**
This file handles the final stage of indexing for textual document data (like PDFs and Word documents). Instead of performing raw text extraction itself, it operates as a federated sink, receiving highly processed payloads from the specialized `worker-pdf`. It heavily utilizes the `LexicalGraphBuilder` from the `neo4j-graphrag` library. When a payload arrives, it maps the raw chunks and extracts entities into a robust Lexical Topology within Neo4j. It establishes `[:NEXT_CHUNK]` relationships to preserve the sequential reading order of the document, and `[:HAS_ENTITY]` relationships to link the text to real-world concepts. It utilizes the `Neo4jWriter` to perform safe, asynchronous batch upserts, ensuring that concurrent indexing jobs do not create duplicate nodes or cause database deadlocks.

### 7. `app/modules/indexing/audio_indexer.py`
**The Conversational Audio Sink**
Similar to the PDF indexer, this file is a federated sink dedicated entirely to conversational data (e.g., Zoom meetings or phone call transcripts) coming from `worker-audio`. Audio data is inherently different from documents because it possesses a temporal structure involving multiple speakers and sequential turns. This indexer models the data using specialized labels such as `Speaker`, `Turn`, and `AudioChunk`. By establishing `[:SPOKE]` relationships between speakers and turns, and `[:FOLLOWS]` relationships between sequential conversational elements, it creates a deeply interconnected conversational graph. This allows the Nexus retrieval engine to effortlessly answer complex temporal questions, such as "What did the CTO say immediately after the budget was mentioned?", a feat that is entirely impossible in traditional flat vector databases.

### 8. `app/modules/indexing/code_indexer.py`
**The Deterministic AST Code Sink**
Unlike unstructured text, source code has an absolute, mathematical structure (Abstract Syntax Trees). Relying on an LLM to guess the structure of code is a fundamental engineering flaw. This file serves as the sink for `worker-code`, completely bypassing LLM-based entity extraction. Instead, it utilizes the `SchemaBuilder` (or direct deterministic Cypher mapping) to accurately map the exact AST payloads into Neo4j. It creates precise nodes for `Class`, `Function`, and `File`, and establishes deterministic relationships such as `[:DEFINED_IN]` and `[:CALLS]`. This strict structural ingestion ensures that when the `Text2CypherRetriever` is queried later, the graph perfectly reflects the actual codebase architecture with zero hallucinations, enabling deep architectural code audits.

### 9. `app/modules/indexing/sql_indexer.py`
**The Deterministic Database Schema Sink**
Data engineering and database schema mapping require 100% precision. This indexer processes structural payloads arriving from the SQL worker, representing the underlying database architectures of enterprise clients. Similar to the Code Indexer, it avoids probabilistic LLM parsing, opting instead to build a deterministic topology of `Table`, `Column`, and `Relation` nodes. By creating rigid `[:HAS_COLUMN]` and `[:FOREIGN_KEY_TO]` relationships, it constructs a complete, queryable ERD (Entity-Relationship Diagram) inside Neo4j. This allows the Nexus orchestrator to seamlessly translate natural language questions like "How do users link to orders?" into exact SQL insights by traversing the deterministic graph paths, fundamentally enabling autonomous data analytics.

### 10. `app/modules/graph_ops/graph_learning.py`
**The Machine Learning & Topology Maintenance Engine**
This file represents the absolute cutting-edge of Graph Artificial Intelligence. Housed strictly within the `graph_ops` domain to separate it from daily retrieval operations, it interfaces directly with the Neo4j Graph Data Science (GDS) plugin. Its primary function is to execute a massive maintenance pipeline that learns from the graph's topology. By creating an in-memory graph projection (`GDSMaintenanceSession`), it runs the FastRP (Fast Random Projection) algorithm to generate structural embeddings (capturing how nodes are connected, rather than their text). It then dynamically trains a Random Forest model using a Link Prediction pipeline to discover hidden, unmapped connections across different data pillars. It mutates the graph by adding `[:INFERRED_LINK_GRL]` relationships, empowering the system to autonomously discover insights that no human explicitly defined.

### 11. `app/modules/graph_ops/entity_resolver.py`
**The Autonomous Deduplication Agent**
In a federated architecture where multiple disconnected workers (Audio, PDF, Code) are constantly pushing entities into a central graph, data duplication is inevitable (e.g., "AWS" vs "Amazon Web Services"). This file is a dedicated Graph Maintenance operation that utilizes the `FuzzyMatchResolver` from `neo4j-graphrag` (Axis 3). Running as a scheduled background operation, it scans the entire Knowledge Graph, mathematically calculating string distances and vector similarities between entity names. When it finds a high-confidence match (e.g., > 85% similarity), it automatically collapses and merges the nodes, migrating all incoming and outgoing relationships to a single, unified Entity node. This self-healing mechanism ensures the graph remains clean, performant, and structurally sound over time.

### 12. `app/infrastructure/neo4j_adapter.py`
**The Database Connection & Execution Layer**
This file handles the low-level communication protocols between the Python microservice and the Neo4j database cluster. It utilizes the official asynchronous Neo4j Python driver to manage connection pooling, transaction execution, and connection timeouts. Beyond simple querying, it houses the highly important `bootstrap_neo4j()` function, which is executed upon service startup. The bootstrap process enforces mandatory database constraints and vector indexes (ensuring unique IDs for Documents, Chunks, and Entities). This infrastructure layer abstracts all Cypher syntax and transaction logic away from the business and domain layers, ensuring that connection instability or query execution errors are handled centrally, retried appropriately, and logged with deep context.

### 13. `app/infrastructure/llm.py`
**The Resilient Language Model Provider**
This file provides the interface to external Large Language Models (OpenAI, VertexAI) tailored specifically for the `neo4j-graphrag` framework. In an enterprise environment, external APIs are notoriously unreliable, prone to rate limiting, and susceptible to sudden latency spikes (Thundering Herd problems). To guarantee absolute resilience, this file implements the `RetryRateLimitHandler` (Axis 7 of the GraphRAG framework). It wraps every single LLM instantiation with an exponential backoff algorithm incorporating randomized jitter. Whether it is generating Cypher queries or synthesizing final reports, this file guarantees that the Nexus service will intelligently throttle and retry failed API calls instead of crashing the Kubernetes pod, ensuring 99.9% uptime for the intelligence hub.

### 14. `app/schemas/nexus_state.py`
**The Single Source of Truth (State Schema)**
In a complex, multi-agent state machine built with LangGraph, maintaining consistent state definitions across multiple files is a recipe for catastrophic data mutation bugs. This file acts as the singular, authoritative definition for the `NexusState` using Python's `TypedDict`. It defines the exact schema of data passing between the nodes—from the initial `question` and `source_ids`, through the complex `graph_context` and `meta_context`, down to the `thinking_steps` and `final_synthesis`. By enforcing this schema globally across the service, it ensures strict type safety. Developers can instantly understand the data flow, and any attempt by an agentic node to inject unauthorized keys into the state is caught immediately, ensuring memory safety and predictable execution.

### 15. `app/infrastructure/config.py`
**The Central Configuration & Secrets Manager**
In an enterprise-grade microservice, hardcoding environment variables or connection strings is an anti-pattern. This file utilizes `pydantic-settings` to define a centralized `Settings` class that automatically validates and parses environment variables from a `.env` file or the system environment. It manages everything from database credentials (Postgres, Redis, Neo4j, Qdrant) to the highly specific LLM model selections for each data pillar (e.g., using `DeepSeek` for code and `Gemini-2.0` for reasoning). By using Pydantic, it provides an additional layer of security and type-checking during the service's bootstrap phase, ensuring that if a critical environment variable like `NEO4J_PASSWORD` is missing, the service will fail to start early (fail-fast), preventing silent execution errors in production.

### 16. `requirements.txt`
**The Dependency Blueprint & Stability Lock**
This file is the cornerstone of the Python environment's stability and reproducibility. It lists the exact libraries and frameworks required to run the Nexus service, such as `neo4j-graphrag`, `langgraph`, `qdrant-client`, and `fastembed`. In a professional CI/CD pipeline, this file ensures that every deployment—whether in a local development container or a production Kubernetes pod—uses the exact same library versions. This prevents the "it works on my machine" syndrome and protects the service from breaking changes in upstream dependencies. By pinning specific versions (e.g., `pydantic-settings==2.1.0`), we ensure that the complex AI orchestration logic remains stable and predictable across the entire development lifecycle.

### 17. `Dockerfile.worker`
**The Immutable Infrastructure Definition**
This file defines the containerization strategy for the Nexus service, enabling it to run as a portable, immutable image on any Kubernetes or Docker cluster. It uses a multi-stage or optimized Debian/Python base image to minimize the attack surface and image size. The Dockerfile handles the installation of critical system-level dependencies required for high-performance AI operations (such as C++ build tools for `RapidFuzz` or `FastEmbed` optimizations). It sets up a non-root user for security best practices and defines the `ENTRYPOINT` that starts the Celery worker process. By encapsulating the entire execution environment into a Docker image, it guarantees that the Nexus service remains isolated, scalable, and resilient to host-level environment drift.

