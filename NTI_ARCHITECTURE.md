# 🏛️ Architecture Documentation

**OpenQ — Autonomous Multi-Pillar Enterprise Data Intelligence Platform**

> An open, composable enterprise intelligence framework — built for organizations sitting on fragmented multi-modal, multi-format data.

---

## Table of Contents

1. [Architectural Principles](#1-architectural-principles)
2. [Clean Architecture per Service](#2-clean-architecture-per-service)
3. [System Overview](#3-system-overview)
4. [4-Layer Service Architecture](#4-4-layer-service-architecture)
5. [LangGraph Pipeline Deep-Dive](#5-langgraph-pipeline-deep-dive)
6. [Knowledge Graph — Neo4j Cross-Pillar Intelligence](#6-knowledge-graph--neo4j-cross-pillar-intelligence)
7. [Security Architecture](#7-security-architecture)
8. [Data Flow — Full Query Lifecycle](#8-data-flow--full-query-lifecycle)
9. [Database Schema](#9-database-schema)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [Observability Stack](#11-observability-stack)
12. [Key Design Decisions](#12-key-design-decisions)

---

## 1. Architectural Principles

**Separation by concern, not by team.**
Each service owns one concept: the API Gateway owns HTTP concerns (auth, routing, validation), the Governance worker owns policy enforcement, each execution pillar owns one data modality. No service does two jobs.

**Celery queues and Event Buses as the communication spine.**
Services communicate asynchronously through named Celery queues over Redis (`api → governance → pillar.sql`), and real-time frontend updates are streamed over WebSockets linked to a Redis Pub/Sub backplane. No direct REST polling.

**Fast gRPC for East-West traffic.**
Critical internal validations (like Rate Limiting and RBAC via the Corporate Service) bypass HTTP entirely, using Protobuf via gRPC for sub-millisecond execution.

**Stateless workers, stateful checkpointing.**
Every Celery worker is ephemeral. LangGraph state is persisted to Redis via `AsyncRedisSaver`. A HITL-paused SQL job survives a worker restart, a pod eviction, or a full cluster reboot.

**Multi-tenant at the data layer, not the application layer.**
A single API deployment serves all tenants. Isolation is enforced by `tenant_id` on every database query — not by separate databases or deployments. Every query is scoped in a SQLAlchemy `where(Model.tenant_id == current_user.tenant_id)` clause.

**Fail loudly in development, fail safely in production.**
The `Settings` validator crashes startup if `SECRET_KEY` or `AES_KEY` are at their default values when `ENV=production`. You cannot accidentally deploy with weak secrets.

**Observability is not optional.**
Every service emits structured logs via `structlog`. Prometheus metrics are scraped at `/metrics`. Grafana dashboards are provisioned automatically — no manual setup required.

**Multi-provider LLM resilience.**
No single LLM vendor is a hard dependency. The LLM factory implements a fallback chain: `OpenRouter (Gemini 2.0 Flash-001) → Groq (Llama-3.3-70B) → Gemini Direct API`. A provider outage degrades gracefully without data loss.

**Knowledge Graph as shared memory.**
All data pillars (code, audio, image, JSON, SQL, PDF) write extracted entities and relationships into a shared Neo4j graph. The Nexus orchestrator reads this graph to produce cross-domain strategic intelligence without re-processing any source.

---

## 2. Clean Architecture per Service

Every microservice follows the same **Clean (Hexagonal) Architecture** layout, enforcing the Dependency Inversion Principle:

```
services/{service}/app/
│
├── domain/                    ← Enterprise Business Rules (innermost ring)
│   └── analysis/
│       └── entities.py        ← AnalysisState (LangGraph TypedDict) — pure Python, no framework deps
│
├── use_cases/                 ← Application Business Rules
│   └── analysis/
│       └── run_pipeline.py    ← Orchestrates: get_pipeline() → Celery dispatch
│
├── modules/                   ← Interface Adapters (Agents & Workflows)
│   └── {modality}/
│       ├── workflow.py        ← LangGraph StateGraph definition
│       ├── agents/            ← Each agent = one graph node (pure async functions)
│       └── tools/             ← LangChain Tools wrapping external calls
│
├── infrastructure/            ← Frameworks & Drivers (outermost ring)
│   ├── config.py              ← Pydantic Settings — reads env vars, validates on startup
│   ├── database/postgres.py   ← SQLAlchemy async engine + session factory
│   ├── llm.py                 ← LLM factory: OpenRouter → Groq → Gemini fallback chain
│   ├── neo4j_adapter.py       ← Neo4j async client — batch upsert, Cypher execution
│   └── adapters/
│       ├── encryption.py      ← AES-256-GCM credential encryption
│       ├── qdrant.py          ← Qdrant async client adapter
│       └── storage.py         ← Tenant-scoped file path resolution
│
├── models/                    ← SQLAlchemy ORM models (maps to PostgreSQL tables)
├── schemas/                   ← Pydantic request/response schemas (API contracts)
└── worker.py                  ← Celery task definitions (entry point per service)
```

**Why this matters:** The `domain/` and `use_cases/` layers have zero imports from `infrastructure/`. Swapping Groq for Claude, or Redis for PostgreSQL as the checkpointer, requires changes only in the `infrastructure/` layer — core agent logic is untouched.

---

## 3. System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL WORLD                                  │
│                                                                            │
│  Browser / API client     OpenRouter / Gemini 2.0 Flash    Qdrant Cloud    │
│       │                           ▲                              ▲         │
└───────┼───────────────────────────┼──────────────────────────────┼─────────┘
        │ HTTPS :8002               │ HTTPS                        │ :6333
┌───────▼───────────────────────────┼──────────────────────────────┼─────────┐
│                   DOCKER COMPOSE NETWORK                          │         │
│                                   │                               │         │
│ ┌───────────────────────────────────────────────────────────────────┐       │
│ │  API GATEWAY  (services/api · :8002)                              │       │
│ │  FastAPI · Async SQLAlchemy · JWT · AES-256-GCM                   │       │
│ └────────────────────────┬──────────────────────────────────────────┘       │
│                          │ Celery tasks via Redis broker                    │
│                   ┌──────▼──────┐                                          │
│                   │    REDIS    │ Broker + result backend                   │
│                   │             │ JWT JTI blacklist                         │
│                   │             │ LangGraph HITL checkpoints                │
│                   │             │ Semantic cache                            │
│                   └──────┬──────┘                                          │
│       ┌───────────────────┼──────────────────────┐                         │
│       ▼                   ▼                       ▼                         │
│ ┌──────────────┐   ┌─────────────┐   ┌────────────────────────────────┐    │
│ │ GOVERNANCE   │   │ worker-sql  │   │ worker-csv / json / pdf / code │    │
│ │ (2-node)     │   │ (12-node)   │   │ audio / image / video / nexus  │    │
│ └──────────────┘   └─────────────┘   └────────────────────────────────┘    │
│                                │ export queue                               │
│                         ┌──────▼──────┐                                    │
│                         │  EXPORTER   │ (Layer 4) PDF/XLSX/JSON            │
│                         └─────────────┘                                    │
│                                                                             │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ PostgreSQL  │  │ Qdrant   │  │  Neo4j   │  │ MongoDB  │  │ Shared   │  │
│  │ :5433       │  │ :6333    │  │  :7687   │  │ :27017   │  │ Volume   │  │
│  │ Metadata DB │  │ RAG      │  │ KG Graph │  │ JSON Docs│  │ ./tenant │  │
│  └─────────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐
│  │  Prometheus  │  │   Grafana    │
│  │  :9090       │  │   :3000      │
│  └──────────────┘  └──────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 4-Layer Service Architecture

### Layer 1 — API Gateway (`services/api`)

The only public-facing service. Handles HTTP, auth, file storage, and Celery dispatch. Never executes analysis logic directly.

**Routing table (11 router modules):**

| Endpoint Group | Responsibility |
|---|---|
| `/auth/*` | JWT issuance, refresh rotation, Redis JTI revocation |
| `/data-sources/*` | File upload, schema profiling, SQL credential encryption, auto-analysis dispatch |
| `/analysis/*` | Job submission, status polling, HITL approval/reject, result retrieval |
| `/knowledge/*` | PDF ingestion → Gemini 2.0 Flash multimodal indexing via Qdrant |
| `/policies/*` | Admin guardrail rule management |
| `/metrics/*` | Job analytics, latency stats, tenant usage |
| `/reports/*` | Async export dispatch + signed download URLs |
| `/groups/*` | Team group management for multi-user tenants |
| `/voice/*` | Voice-to-text query submission (audio → transcription → analysis queue) |
| `/health` | Deep health check (PostgreSQL + Redis + Celery workers) |

**Key infrastructure modules:**

```
infrastructure/
├── config.py           Pydantic Settings — validates env vars on startup
│                       Crashes in production if SECRET_KEY or AES_KEY are default
├── security.py         JWT access (30min) + refresh (7 days) + bcrypt + JTI
├── sql_guard.py        3-layer SQL injection prevention
├── middleware.py       CORS · rate limiting (slowapi) · security headers
├── token_blacklist.py  Redis-backed JTI revocation set (TTL = token remaining lifetime)
├── llm.py              Multi-provider factory: OpenRouter → Groq → Gemini
└── adapters/
    ├── encryption.py   AES-256-GCM — encrypt/decrypt SQL connection strings
    ├── qdrant.py       Async Qdrant client — multi-vector upsert + similarity search
    └── storage.py      Tenant-scoped file path resolution
```

**Self-healing startup:** The `lifespan` context manager acquires a PostgreSQL advisory lock, then runs idempotent `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every deploy. Lock timeout is 5s per statement. Adding a new column = deploying new code, no migration script, no downtime.

---

### Layer 2 — Governance (`services/governance`)

Dedicated Celery worker on the `governance` queue. Every analysis job passes through here before reaching any execution pillar.

**LangGraph graph (2 nodes):**
```
START → [intake_agent] → check_intake → [guardrail_agent] → route_to_pillar → END
                                │
                                └── clarification_needed → END (asks user to rephrase)
```

**Intake Agent responsibilities:**
- Classify question intent: `trend | comparison | ranking | correlation | anomaly`
- Extract named entities (table names, column names, date ranges, metric names)
- Detect ambiguous or underspecified questions, request clarification
- Assign complexity index (1–5) based on entity count and join requirements

**Guardrail Agent responsibilities:**
- Load active policies for the tenant from PostgreSQL
- LLM semantic check: does this question violate any admin policy?
- PII detection: would the answer expose sensitive columns?
- If violation: set job to `error` status with a human-readable explanation

**Bypass path:** `auto_analysis` system user (`user_id == "auto_analysis"`) skips governance — background analyses triggered on upload are system-generated and policy-safe by construction.

---

### Layer 3 — Execution Pillars (8 specialized workers)

Each pillar is a separate Docker container with its own `requirements.txt`, independently scalable on Kubernetes.

All workers share the same **Clean Architecture layout** and use `structlog` for structured JSON logging with automatic `job_id` context binding.

```
worker-sql    → queues: pillar.sql, pillar.sqlite, pillar.postgresql
worker-csv    → queue:  pillar.csv
worker-json   → queue:  pillar.json
worker-pdf    → queue:  pillar.pdf
worker-code   → queue:  pillar.code
worker-audio  → queue:  pillar.audio
worker-image  → queue:  pillar.image
worker-video  → queue:  pillar.video
worker-nexus  → queue:  pillar.nexus
```

---

### Layer 4 — Exporter (`services/exporter`)

Async worker on the `export` queue. Receives completed `AnalysisResult` objects and renders them to:
- **PDF** — formatted report with charts as static images
- **XLSX** — data snapshot in Sheet 1, recommendations in Sheet 2
- **JSON** — raw result envelope for downstream consumption

Output files are written to `tenant_uploads/{tenant_id}/exports/` and served via signed download URLs through the API Gateway.

---

## 5. LangGraph Pipeline Deep-Dive

### SQL Pipeline — 12 Nodes (Cyclic StateGraph)

The most complex pipeline. Features HITL approval, zero-row self-healing reflection, hybrid PDF+SQL fusion, and semantic result caching.

```
START
  │
  ▼
[data_discovery]         ← Schema mapper: tables, columns, PKs, FKs, sample values,
  │                         low-cardinality enums, Mermaid ERD generation,
  │                         schema_selector compresses to relevant tables only
  ▼
[analysis_generator]     ← ReAct agent: retrieves golden SQL from insight_memory,
  │                         generates ANSI SELECT + execution plan annotation,
  │                         sql_validator: syntax pre-check before routing
  ▼
route_after_generator
  ├── error + retry < 3  → [reflection]  ← Injects corrective hint into state
  ├── auto_analysis=True → [execution]   ← Bypasses HITL entirely
  └── user job           → [human_approval]
                               │  INTERRUPT fires (interrupt_after=["human_approval"])
                               │  Full graph state serialized to Redis (AsyncRedisSaver)
                               │  Job status → "awaiting_approval"
                               │  Generated SQL surfaced to admin in UI
                               │
                               │  POST /analysis/{id}/approve
                               │  State patched: {approval_granted: True}
                               │  Graph resumed from Redis checkpoint
                               ▼
                          [execution]    ← Runs approved SQL, fetches ≤1,000 rows
                               │           Captures: row_count, column_names, data_snapshot
                               │
                          route_after_execution
                           ├── error or row_count=0 + retry < 3 → [reflection]
                           │      │  Compares SQL literals against low_cardinality_values
                           │      │  Detects case mismatches (e.g. "q4" vs "Q4")
                           │      │  Injects correction hint + increments retry_count
                           │      └──► [execution]  (re-executes fixed SQL directly)
                           │
                           └── success → [hybrid_fusion]
                                             │  If kb_id present: Qdrant vector search
                                             │  Retrieves PDF context related to SQL result
                                             │  Merges kb_context into state
                                             ▼
                                       [visualization]   ← Selects chart type per intent + data shape
                                             │              Generates ECharts/Plotly JSON spec
                                             ▼
                                          [insight]       ← 3–5 sentence executive summary
                                             │              Grounded in actual row values + kb_context
                                             ▼
                                          [verifier]      ← Quality gate: insight vs data
                                             │              Prevents hallucinated insights
                                             ▼
                                      [recommendation]   ← 3 actionable next steps
                                             ▼
                                        [save_cache]     ← Saves {question → result} to semantic cache
                                             ▼
                                   [output_assembler]    ← Builds final JSON envelope
                                             │              Writes AnalysisResult to PostgreSQL
                                             │              Updates job status → "done"
                                             ▼
                                            END
```

**Self-healing mechanisms:**
- **Zero-Row Reflection:** `row_count=0` triggers `reflection_context` injection. The reflection node analyzes the SQL, compares literals against `low_cardinality_values`, detects case mismatches, and injects a corrective hint. Max 3 retries.
- **Error Reflection:** Any runtime SQL error routes to `reflection` → `execution` (bypasses `analysis_generator` to avoid generating a simpler fallback query).
- **Verifier Agent:** Quality gate between insight and recommendation — rejects insights not supported by actual data.

---

### CSV Pipeline — 11 Nodes (Cyclic StateGraph)

```
START
  │
  ▼
[data_discovery]         ← profile_dataframe: dtype inference, null ratio, unique counts,
  │                         outlier density (IQR method), data_quality_score computation
  │
needs_cleaning? (data_quality_score < 0.9)
  ├── YES → [data_cleaning]   ← clean_dataframe: null imputation (median/mode),
  │              │               type coercion, outlier flagging (_outlier column)
  │              ▼
  └── NO  → [guardrail]       ← Validates question safety before analysis
                 │
                 ▼
            [analysis]        ← Selects tool by intent: compute_trend, compute_ranking,
                 │               compute_correlation. Executes Pandas operations.
                 │               Returns summary stats + structured data
                 │
check_analysis_result
  ├── error + retry < 3 → [reflection]  ← Repairs Python/Pandas code errors
  │                            └──► [analysis]  (retry loop)
  └── success → [visualization]  ← Plotly/ECharts chart spec
                     │
                     ▼
                [insight]         ← Executive summary grounded in computed statistics
                     ▼
                [verifier]        ← Quality gate
                     ▼
             [recommendation]    ← 3 next steps based on statistical findings
                     ▼
         [output_assembler]      ← Final JSON → PostgreSQL write
                     ▼
             [save_cache]        ← Semantic cache save → END
```

---

### JSON Pipeline — 10 Nodes (Directed Cyclic StateGraph)

Backed by **MongoDB** for document intelligence over semi-structured JSON stores, with **Qdrant** (768d vectors) for semantic retrieval.

```
START
  │
  ▼
[data_discovery]     ← Connects to MongoDB, samples documents, extracts schema structure,
  │                     identifies nested keys and array shapes
  ▼
[guardrail]          ← Policy enforcement before any data access
  ▼
[analysis]           ← Semantic decomposition of complex nested JSON schemas.
  │                     MongoDB aggregation pipeline generation + execution.
  │                     Qdrant (768d vectors) for RAG-augmented context retrieval.
  │
check_analysis_result
  ├── error + retry < 3 → [reflection]  ← Fixes MongoDB query errors
  │                            └──► [analysis]
  └── success → [visualization]
                     ▼
                [insight]
                     ▼
                [verifier]
                     ▼
            [recommendation]
                     ▼
          [output_assembler]
                     ▼
             [save_cache] → END
```

---

### PDF Pipeline — 10 Nodes (Orchestrator-Worker StateGraph)

The most architecturally complex pipeline. A master orchestrator routes between **three specialist synthesis engines** based on document type. It utilizes **Parent-Child Chunking** for dense Context preservation and semantic JSON Ontologies extracted via Vision-Models.

```
START
  │
  ▼
[refine]             ← query_refiner_agent: rewrites the question for optimal RAG retrieval,
  │                     expands abbreviations, clarifies ambiguous terms
  ▼
[router]             ← router_agent: classifies intent
  │
route_after_router
  ├── "greeting" → [chat]   ← Direct LLM chat, no retrieval needed
  └── "analysis" → [retrieval]
                       │
                       ▼
                  [retrieval]       ← adaptive_retrieval_agent: Qdrant vector search,
                       │               scores chunk relevance, detects retrieval failures
                       │
               route_after_retrieval
                ├── reflection_needed=True → [refine]  ← Loops back to refine query
                ├── mode="deep_vision"    → [vision_synthesis]
                ├── mode="fast_text"      → [text_synthesis]
                └── mode="hybrid"         → [ocr_synthesis]

           [vision_synthesis]    ← Gemini 2.0 Flash Vision: PDF pages rendered as JPEG images,
                │                   base64-encoded, sent to multimodal LLM for synthesis
                │
           [text_synthesis]      ← Fast text extraction + LLM synthesis for clean PDFs
                │
           [ocr_synthesis]       ← Hybrid OCR (Tesseract/PaddleOCR) for scanned documents
                │
                └───────────────► [verifier]   ← Anti-hallucination agent: checks answer
                                       │           grounded in retrieved context
                                  route_after_verifier
                                   ├── verified=False + retry < 2 → re-route to synthesis engine
                                   └── verified=True → [analyst]
                                                           │
                                                           ▼
                                                    [output_assembler] → END

           [chat] → [output_assembler] → END
```

**Three Synthesis Engines:**

| Engine | Mode | Use Case |
|---|---|---|
| `vision_synthesis` (Gemini 2.0 Flash Vision) | `deep_vision` | PDFs with charts, tables, diagrams — preserves visual layout |
| `text_synthesis` | `fast_text` | Clean text-based PDFs — fast extraction, sub-second latency |
| `ocr_synthesis` | `hybrid` | Scanned documents, low-quality images — OCR pre-processing |

---

### Code Pipeline — 8 Nodes (Cyclic StateGraph, Neo4j)

A specialized pipeline analyzing full source code repositories mapped as an Abstract Syntax Tree (AST) in Neo4j. Pure Cypher-based reasoning — no file reading at query time.

```
START
  │
  ▼
[discovery]     ← Neo4j APOC connection: builds graph schema description,
  │               discovers labels (Class, Function, File), relationship types,
  │               live stats (node counts, avg degree), sample node summaries
  ▼
[generator]     ← LLM: transforms natural-language question → Cypher query
  │               Uses schema description as context for accurate node/rel targeting
  │
route_after_generator
  ├── error + retry < MAX_RETRIES  → [reflection] → [generator]  (retry loop)
  ├── error + retry >= MAX_RETRIES → END
  └── no error → [execution]
                     │  Runs Cypher against Neo4j via shared pool singleton
                     │  No new TCP connections per request
                     │
route_after_execution
  ├── error + retry < MAX_RETRIES → [reflection] → [generator]
  └── no error → [insight]
                     │  LLM: execution_results + code snippets → narrative explanation
                     ▼
                 [memory]          ← memory_manager_agent: sliding window episodic summary
                     ▼
                 [save_cache]      ← Saves question+Cypher+result to semantic cache
                     ▼
                 [assembler]       ← Final JSON → PostgreSQL write → END
```

---

### Audio Pipeline — 9 Nodes (Linear StateGraph, OpenRouter Multimodal)

A specialized pipeline designed for multimodal processing of audio directly via native audio ingestion (Gemini 2.5 Flash), completely bypassing traditional NLP transcription layers.

```
START
  │
  ▼
[profiler]      ← Validates duration, formats (.wav, .mp3), size limits
  │               and detects base channels and sample rates.
  ▼
[preprocessor]  ← Normalizes dbFS, converts to Mono 16kHz, splits silence segments
  │               (using `pydub` and `silero-vad`), encodes to base64.
  ▼
[transcription] ← OpenRouter `gemini-2.5-flash-preview` natively processes
  │               Base64 audio without intermediate TTS. Outputs raw transcript
  │               and raw speaker turns (`SPEAKER_01`).
  │
route_after_transcription
  ├── error → END
  └── success → [diarization]
                   │
                   ▼  (Contextual name resolution mapping SPEAKER_XX → "Name")
            [entity_extractor]
                   │  LLaMA 3.1 8B (Text): Pulls Topics, Action Items, Key Quotes
                   ▼
             [summarizer]
                   │  Gemini 2.0 Flash Lite: Generates 3-sentence Exec Summary
                   ▼
              [evaluator]
                   │  Local SLM: ms-marco (Relevance) + nli-deberta (Attribution)
                   ▼
             [memory_manager]
                   │  Qdrant (Vectors) + Neo4j (Graph mapping Speakers/Entities)
                   ▼
           [output_assembler] → END
```

---

### Image / Video Pipelines — Direct Task (Gemini Multimodal)

These two workers use a **direct Celery task** pattern rather than a LangGraph graph, because their primary job is discovery/indexing (not iterative reasoning).

**Image / Video workers** follow the pattern — upload → Gemini multimodal call → entity extraction → Neo4j sync → status update.

---

### Nexus Pipeline — 6 Nodes (Federated Orchestrator)

The strategic intelligence layer. Reads the shared Neo4j knowledge graph and utilizes **Multi-Query RAG-Fusion** accompanied by a **Cross-Encoder Re-Ranker** to produce a 5-pillar Executive Strategic Intelligence Report without Hallucinations or Context Sprawl.

```
START
  │
  ▼
[router]         ← nexus_router: routes based on query complexity
  │               "explore" → [explorer] → [orchestrator]
  │               "direct_query" → [orchestrator]
  │               "finalize" → [synthesizer]
  ▼
[explorer]       ← graph_explorer: discovers available pillars and Neo4j context
  ▼
[orchestrator]   ← pillar_orchestrator (inner StateGraph):
  │               Node 1 — discovery_node: forge_cross_source_links() in Neo4j
  │                         Creates Code↔SQL, Entity↔Target, Chunk↔Mention relationships
  │               Node 2 — gather_context_node:
  │                         Pulls all Neo4j entities + cross-links per source_id
  │                         Fetches Postgres schema/metadata per source
  │               Node 3 — synthesis_node:
  │                         Buckets entities by pillar type (sql/csv/json/pdf/codebase)
  │                         Builds structured cross-pillar context block
  │                         LLM (Gemini 2.0 Flash) generates 5-section report:
  │                           1. Executive Summary
  │                           2. 5-Pillar Cross-Domain Findings
  │                           3. Compliance & Policy Assessment
  │                           4. Data Architecture Risks & Anomalies
  │                           5. Strategic Recommendations
  ▼
[synthesizer]    ← synthesis_engine: final cross-pillar consolidation
  ▼
[memory]         ← memory_manager: episodic memory via Qdrant semantic similarity
  ▼
[save_cache]     ← saves question+synthesis to semantic cache → END
```

---

### Governance Pipeline — 2 Nodes

```
START → [intake_agent] → check_intake → [guardrail_agent] → route_to_pillar → END
                               │
                               └── clarification_needed → END
```

---

## 6. Knowledge Graph — Neo4j Cross-Pillar Intelligence

Neo4j acts as the **shared organizational memory** across all data pillars. Every worker writes entities into the graph. The Nexus orchestrator reads and forges cross-pillar relationships.

### Entity Types by Pillar

| Pillar | Neo4j Node Labels |
|---|---|
| `worker-code` | `Class`, `Function`, `File`, `Module` |
| `worker-audio` | `Speaker`, `Topic`, `Entity` (person/company/product) |
| `worker-image` | `Object`, `Scene`, `Entity` |
| `worker-video` | `Scene`, `Event`, `Entity` |
| `worker-json` | `JSONField`, `JSONDocument` |
| `worker-sql` / `worker-csv` | `DatasetColumn`, `Table` |
| `worker-pdf` | `Chunk`, `DocumentPage` |

### Cross-Pillar Relationship Types

| Relationship | Connects |
|---|---|
| `REPRESENTS_DATA` | Code `Class` → SQL `Table` |
| `ENTITY_TARGET` | Audio/Image `Entity` → SQL `Table` or `DatasetColumn` |
| `CHUNK_MENTION` | PDF `Chunk` → Code `Function` or SQL `Table` |

### Forge Algorithm (`Neo4jAdapter.forge_cross_source_links`)

```
For all source_id pairs:
  1. Match Class nodes (code) → Table nodes (sql) by name similarity → CREATE :REPRESENTS_DATA
  2. Match Entity nodes (audio/image) → Table/Column nodes (sql) by name similarity → CREATE :ENTITY_TARGET
  3. Match Chunk nodes (pdf) → Function/Table nodes → CREATE :CHUNK_MENTION
```

---

## 7. Security Architecture

### JWT Authentication Flow

```
POST /auth/register or /auth/login
  └── Returns: access_token (30min) + refresh_token (7 days)
               Both tokens contain a JTI (JWT ID) — a unique UUID per token

Protected Request
  └── Authorization: Bearer {access_token}
      └── Verify signature → decode claims → check JTI not in Redis blacklist

Access Token Expired
  └── POST /auth/refresh {refresh_token}
      └── Verify refresh_token signature + expiry + JTI not in blacklist
          └── DELETE old JTI from Redis (rotation — old token dead immediately)
              └── Issue new access_token + new refresh_token

POST /auth/logout {refresh_token}
  └── ADD refresh_token JTI to Redis blacklist (SET with TTL = remaining token lifetime)
      └── Token is permanently dead — even if captured, it is worthless
```

### SQL Guard — 3 Layers in Sequence

```python
# services/api/app/infrastructure/sql_guard.py

def validate_sql(query: str) -> None:
    stripped = query.strip().upper()

    # Layer 1: Allowlist — must start with SELECT or WITH (CTEs)
    if not stripped.startswith(("SELECT", "WITH")):
        raise ValueError("Only SELECT queries are permitted")

    # Layer 2: Blocklist — reject dangerous DML/DDL keywords anywhere
    DANGEROUS_PATTERN = r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE|GRANT|REVOKE|MERGE|CALL|XP_|SP_)\b"
    match = re.search(DANGEROUS_PATTERN, query, re.IGNORECASE)
    if match:
        raise ValueError(f"Forbidden SQL keyword: {match.group()}")

    # Layer 3: LLM Semantic Guardrail (runs in governance worker)
    # Policy-aware semantic check: catches "comp" when policy says "never expose salary"
    # Admin configures in plain English via /policies endpoint
```

### AES-256-GCM Credential Encryption

```python
# services/api/app/infrastructure/adapters/encryption.py

def encrypt_json(data: dict, key: bytes) -> str:
    plaintext = json.dumps(data).encode()
    nonce = os.urandom(12)         # 96-bit random nonce
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()
```

The `AES_KEY` env var is the only key material. Loss of the key = permanent loss of all encrypted SQL credentials by design. Migrate to a secrets manager by replacing `encrypt_json/decrypt_json` with SDK calls.

### Multi-Provider LLM Fallback Chain

```python
# services/{worker}/app/infrastructure/llm.py

def get_llm(temperature=0, model=None) -> BaseChatModel:
    # Primary: OpenRouter (Gemini 2.0 Flash-001)
    # Fallback 1: Groq (Llama-3.3-70B)
    # Fallback 2: Gemini Direct API (gemini-2.0-flash-exp)

    llm = _make_openrouter("google/gemini-2.0-flash-001")
    fallbacks = [_make_groq("llama-3.3-70b-versatile"), _make_gemini("gemini-2.0-flash-exp")]
    return llm.with_fallbacks(fallbacks)
```

---

## 8. Data Flow — Full Query Lifecycle

```
User types: "What are the top 5 products by revenue in Q4?"
  │
  │  POST /api/v1/analysis/query { source_id, question, kb_id }
  ▼
API Gateway
  1. Verify JWT → extract user_id, tenant_id, role
  2. Verify data_source.tenant_id == user.tenant_id
  3. INSERT AnalysisJob(status="pending") → commit
  4. governance_task.apply_async(args=[job_id], queue="governance")
  5. Return { job_id, status="pending" } ← client gets this immediately

Redis receives task
  │
  ▼
Governance Worker
  6. Fetch job + data source from PostgreSQL
  7. Decrypt config_encrypted → connection_string (in memory only, never logged)
  8. intake_agent → intent="ranking", entities=["products","revenue","Q4"]
  9. guardrail_agent → load tenant policies → no violations
  10. pillar_task.apply_async(args=[job_id], queue="pillar.sql")

SQL Worker
  11. Build LangGraph StateGraph with AsyncRedisSaver checkpointer
  12. [data_discovery] → schema: tables=sales,products; low_cardinality: quarter=["Q1","Q2","Q3","Q4"]
  13. [analysis_generator] →
      SELECT p.name, SUM(s.revenue) AS total
      FROM sales s JOIN products p ON s.product_id = p.id
      WHERE s.quarter = 'Q4'
      GROUP BY p.name ORDER BY total DESC LIMIT 5
  14. route_after_generator → user job → [human_approval] INTERRUPT
  15. graph state serialized to Redis via AsyncRedisSaver (key: checkpoint:{thread_id})
  16. Job status → "awaiting_approval". Worker exits cleanly (Celery task slot freed).

Client polls GET /analysis/{job_id}
  ← { status: "awaiting_approval", generated_sql: "SELECT p.name..." }

Admin reviews SQL in UI. Clicks "Approve".
  │
  │  POST /api/v1/analysis/{job_id}/approve
  ▼
API Gateway
  17. Verify admin role
  18. Update job status → "running"
  19. aupdate_state({approval_granted: True}) → patches Redis checkpoint
  20. pillar_task.apply_async(args=[job_id], queue="pillar.sql")

SQL Worker resumes from Redis checkpoint
  21. [execution] → runs approved SQL → row_count=5
  22. [hybrid_fusion] → kb_id=null → skip Qdrant
  23. [visualization] → ECharts bar chart: products vs revenue
  24. [insight] → "Product A led Q4 with $2.3M, 28% of quarterly total..."
  25. [verifier] → insight references row values ✓
  26. [recommendation] → ["Prioritize Product A inventory...", ...]
  27. [save_cache] → saves question+result to semantic cache (Qdrant)
  28. [output_assembler] → build AnalysisResult JSON
  29. INSERT AnalysisResult → UPDATE job status → "done"

Client polls GET /analysis/{job_id} ← { status: "done" }
Client fetches GET /analysis/{job_id}/result
  ← { charts, insight_report, exec_summary, recommendations, follow_up_suggestions, data_snapshot }
```

**Total time (typical):** 8–18 seconds from query submission to result, excluding HITL pause.

---

## 9. Database Schema

**Entity Relationship:**

```
tenants ──< users
        ──< data_sources ──< analysis_jobs ──── analysis_results (1:1)
        ──< knowledge_bases
        ──< policies
        ──< team_groups

analysis_jobs >── knowledge_bases (optional FK for hybrid PDF fusion)
analysis_jobs >── users (FK: user_id)
users >── team_groups (FK: group_id)
```

**Key design decisions:**

`config_encrypted TEXT` — credentials stored as a single AES-256-GCM encrypted blob. Plaintext never touches disk.

`thinking_steps JSON` — every LangGraph node output captured per job. Powers the "Reasoning" panel in the UI — full audit trail of agent cognition.

`auto_analysis_json JSON` — 5 pre-generated analyses computed on upload. Displayed instantly on first open. First-impression latency matters for adoption.

`low_cardinality_values` (in `schema_json`) — sampled enum values per column, used by zero-row reflection to detect case mismatches without re-querying the database.

`complexity_index INTEGER` — assigned by the intake agent (1–5 scale). Drives UI complexity indicators and future SLA routing.

`indexing_status VARCHAR` — tracks Neo4j / Qdrant indexing status for audio, image, video, and code sources. Drives the availability of Nexus cross-pillar intelligence.

---

## 10. Infrastructure & Deployment

### Kubernetes Namespace Layout

All K8s resources are split across **two namespaces** for security isolation:

| Namespace | Contents |
|---|---|
| `openq-core` | API Gateway, Frontend, Governance worker, Exporter |
| `openq-workers` | All Celery pillar workers (SQL, CSV, JSON, PDF, Code, Nexus, Multimedia) |

### K8s Directory Structure (numbered apply order)

```
k8s/
├── 01-namespaces.yaml          # openq-core + openq-workers namespaces
├── 02-config.yaml              # ConfigMap (LLM models, auth config) + Secret
├── 03-core/
│   ├── api-gateway.yaml          # Deployment (2 replicas) + ClusterIP Service
│   └── frontend.yaml             # React SPA Deployment (2 replicas) + ClusterIP Service
├── 04-workers/
│   ├── exporter-governance.yaml  # Exporter + Governance (co-located, openq-core)
│   ├── worker-sql.yaml           # pillar.sql/.sqlite/.postgresql, concurrency=4
│   ├── worker-csv.yaml           # pillar.csv
│   ├── worker-json.yaml          # pillar.json
│   ├── worker-pdf.yaml           # TWO deployments: indexing (queue:knowledge) + analysis (queue:pillar.pdf)
│   ├── worker-code.yaml          # pillar.code, Neo4j URI injected
│   ├── worker-nexus.yaml         # pillar.nexus, Neo4j + Qdrant URIs injected
│   └── worker-multimedia.yaml    # 3 containers in 1 pod: audio + image + video workers
└── 05-ingress/
    └── alb-ingress.yaml          # AWS ALB Ingress: /api → api-service, / → frontend-service
```

**Apply order:**
```bash
kubectl apply -f k8s/01-namespaces.yaml
kubectl apply -f k8s/02-config.yaml
kubectl apply -f k8s/03-core/
kubectl apply -f k8s/04-workers/
kubectl apply -f k8s/05-ingress/alb-ingress.yaml
```

### Worker Resource Limits (actual from manifests)

| Deployment | Namespace | Queues | CPU limit | Memory limit | Notes |
|---|---|---|---|---|---|
| `api-gateway` | `openq-core` | — (HTTP) | 1000m | 2Gi | 2 replicas |
| `frontend` | `openq-core` | — (HTTP) | 500m | 512Mi | 2 replicas |
| `governance` | `openq-core` | `governance,celery` | 500m | 1Gi | concurrency=2 |
| `exporter` | `openq-core` | `export` | 500m | 1Gi | concurrency=2 |
| `worker-sql` | `openq-workers` | `pillar.sql/.sqlite/.postgresql` | 1500m | 2Gi | concurrency=4 |
| `worker-csv` | `openq-workers` | `pillar.csv` | — | — | — |
| `worker-json` | `openq-workers` | `pillar.json` | — | — | — |
| `worker-pdf-indexing` | `openq-workers` | `knowledge` | 3000m | 14Gi | HuggingFace model cache |
| `worker-pdf-analysis` | `openq-workers` | `pillar.pdf` | 3000m | 14Gi | concurrency=3 |
| `worker-code` | `openq-workers` | `pillar.code` | 1500m | 4Gi | Neo4j URI injected |
| `worker-nexus` | `openq-workers` | `pillar.nexus` | 1000m | 2Gi | Neo4j + Qdrant URIs |
| `worker-multimedia` | `openq-workers` | `pillar.audio/image/video` | — | — | 3 containers in 1 Pod |

> **PDF worker is split into 2 deployments:** `worker-pdf-indexing` handles knowledge base ingestion (`queue: knowledge`), `worker-pdf-analysis` handles analysis queries (`queue: pillar.pdf`). Both use the same Docker image with `WORKER_TYPE` env var to switch behaviour.

### Authentication — Local vs Production

| Strategy | `ENV` value | Mechanism |
|---|---|---|
| **JWT (local/dev)** | `development` | Local `python-jose` signing, bcrypt, Redis JTI blacklist |
| **Auth0 (production)** | `production` | `AUTH_STRATEGY=auth0`, JWKS endpoint validation, SSO + MFA |

In production, `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `AUTH0_CLIENT_ID` are provided via ConfigMap (`02-config.yaml`). Secrets (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `SECRET_KEY`, `AES_KEY`) are stored in a Kubernetes Secret (`openq-secrets`).

### Per-Pillar LLM Model Configuration

Each worker consumes its own `LLM_MODEL_*` variable from the ConfigMap:

| ConfigMap Key | Production Value | Rationale |
|---|---|---|
| `LLM_MODEL` | `google/gemini-2.0-flash-001` | Default — CSV, JSON, Governance |
| `LLM_MODEL_SQL` | `google/gemini-2.0-flash-001` | High-accuracy SQL generation |
| `LLM_MODEL_PDF` | `google/gemini-2.0-flash-lite-001` | Cost-optimised for large PDF batches |
| `LLM_MODEL_CODE` | `deepseek/deepseek-chat-v3-0324` | Code-native model for Cypher generation |
| `LLM_MODEL_NEXUS` | `google/gemini-2.0-flash-001` | Strategic synthesis — high capacity |
| `LLM_MODEL_FAST` | `meta-llama/llama-3.2-3b-instruct` | Audio/video metadata — lightweight |
| `LLM_MODEL_VISION` | `meta-llama/llama-3.2-11b-vision-instruct` | Image/video visual understanding |

### AWS Ingress — ALB

```yaml
# k8s/05-ingress/alb-ingress.yaml
annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
rules:
  - /api  → api-service:80
  - /     → frontend-service:80
# Recommended: add ACM certificate ARN for HTTPS
```

### Image Registry — ECR

All production Docker images follow the naming convention:
```
omarabdelhamidaly/openq-api:latest
omarabdelhamidaly/openq-governance:latest
omarabdelhamidaly/openq-worker-sql:latest
omarabdelhamidaly/openq-worker-csv:latest
omarabdelhamidaly/openq-worker-json:latest
omarabdelhamidaly/openq-worker-pdf:latest
omarabdelhamidaly/openq-worker-code:latest
omarabdelhamidaly/openq-worker-nexus:latest
omarabdelhamidaly/openq-worker-audio:latest
omarabdelhamidaly/openq-worker-image:latest
omarabdelhamidaly/openq-worker-video:latest
omarabdelhamidaly/openq-exporter:latest
omarabdelhamidaly/openq-frontend:latest
```

### Terraform — AWS Infrastructure Provisioning

```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
aws eks update-kubeconfig --region us-east-1 --name openq-eks-cluster
```

| Module | AWS Resource | Configuration |
|---|---|---|
| `vpc` | VPC + Subnets + NAT Gateway | CIDR `10.0.0.0/16`, public + private subnets |
| `eks` | EKS Cluster + Node Group | `openq-eks-cluster`, `t3.large` worker nodes, `us-east-1` |
| `database` | Aurora Serverless v2 (PostgreSQL) | 0.5–2.0 ACUs — auto-scales to zero when idle |
| `cache` | ElastiCache Redis | Managed Redis for Celery broker + HITL state checkpoints |
| `ecr` | Elastic Container Registry | Stores all `omarabdelhamidaly/openq-*` images |
| `iam-cicd` | IAM Role + Policy | Least-privilege role for CI/CD pipeline (GitHub Actions) |

**Terraform outputs:**
```
vpc_id                 → VPC resource ID
eks_cluster_endpoint   → Kubernetes API server endpoint
aurora_db_endpoint     → PostgreSQL host (replaces DATABASE_URL)
redis_primary_endpoint → ElastiCache host (replaces REDIS_URL)
kubeconfig_command     → aws eks update-kubeconfig --region us-east-1 --name openq-eks-cluster
```

> **Production migration path:** replace `DATABASE_URL` in `02-config.yaml` with `aurora_db_endpoint`, and `REDIS_URL` with `redis_primary_endpoint` from Terraform outputs. Credentials should be moved to AWS Secrets Manager or HashiCorp Vault.

---

## 11. Observability Stack

### Prometheus

Scrapes metrics from the API Gateway at `/metrics` (port `8000` internal, mapped to `8002` externally):

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'analyst-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']   # via redis_exporter sidecar

  # Optional: Celery Flower real-time task monitor
  # - job_name: 'flower'
  #   static_configs:
  #     - targets: ['flower:5555']
```

**Key metric names:**
```
insightify_api_requests_total{method, endpoint, status_code}
insightify_api_request_duration_seconds{method, endpoint}
insightify_jobs_total{status, intent, source_type}
insightify_jobs_duration_seconds{pipeline, node}
insightify_queue_depth{queue_name}
```

### Grafana

Pre-provisioned dashboards (no manual setup — auto-loaded via `grafana/provisioning/`):

| Dashboard | Key Panels |
|---|---|
| **Platform Overview** | Active jobs, error rate, p50/p95/p99 latency, queue depths |
| **Pipeline Performance** | Per-node latency breakdown across all worker pipelines |
| **Tenant Analytics** | Jobs per tenant, data source distribution, intent breakdown |
| **Security** | Rate limit hits, auth failures, JWT revocations |

Access: `http://localhost:3000` — admin/admin (change in production).

### Structured Logging

All services emit JSON logs via `structlog` with automatic context variable binding:

```json
{
  "timestamp": "2026-04-15T09:05:12.334Z",
  "level": "info",
  "service": "worker-sql",
  "tenant_id": "7c9e6679-...",
  "job_id": "job-uuid",
  "node": "execution",
  "row_count": 5,
  "duration_ms": 423
}
```

---

## 12. Key Design Decisions

### Why Clean Architecture per service?

Each microservice could be a simple script. Instead, we applied the Dependency Inversion Principle: `domain/` and `use_cases/` layers import nothing from `infrastructure/`. This means swapping Groq for Gemini, or switching from Redis to PostgreSQL as the LangGraph checkpointer, requires changes only in the outermost ring. Core agent logic — the expensive-to-test, expensive-to-reason-about part — is isolated from framework churn.

### Why Celery queues between layers instead of HTTP?

HTTP between microservices creates tight coupling — if governance is down, analysis submissions fail immediately. Celery queues decouple producers from consumers: the API accepts jobs even when workers are restarting. Workers scale independently by adjusting `--concurrency`. Dead-letter queues catch and retry failed tasks without code changes.

### Why one database for all tenants?

Multi-database tenancy scales to thousands of tenants but requires a connection pool of thousands of connections and per-tenant migration management. Single-database with `tenant_id` scoping scales to hundreds of tenants with standard pooling and a single migration run. The isolation guarantee is equivalent — every query is WHERE-scoped. The only risk is an accidentally-omitted `tenant_id` filter, mitigated by a central `get_current_user` dependency that enforces the scope.

### Why Redis checkpointer for HITL?

A Celery task cannot be "paused" — it must terminate and resume. LangGraph's `AsyncRedisSaver` serializes the full graph state to Redis when `interrupt_after=["human_approval"]` fires. On resume (`POST /approve`), the graph is reconstructed from the checkpoint and continues from exactly where it paused. This makes HITL durable across worker restarts, pod evictions, and cluster reboots.

### Why AES-256-GCM instead of a secrets manager?

A secrets manager is the right answer at scale. AES-256-GCM in the database is a defensible interim choice: production-grade encryption, zero external dependencies, simple to audit. The migration path is clean — replace `encrypt_json/decrypt_json` with secrets manager SDK calls.

### Why Gemini 2.0 Flash for PDF synthesis?

Traditional PDF RAG chunks text and embeds it — destroying visual layout, tables, and charts. Gemini 2.0 Flash is natively multimodal: PDF pages are rendered as JPEG images and sent directly to the model, which understands both layout and text simultaneously. For enterprise documents (financial reports, technical manuals), visual layout carries as much meaning as raw text. This approach requires no OCR pre-processing for clean PDFs and no separate embedding model for visual content.

### Why Neo4j for the Knowledge Graph?

Relational databases model entities well but express relationships poorly. The cross-pillar intelligence Nexus needs to find that a `Function` in the codebase `REPRESENTS_DATA` in a SQL `Table` that is `MENTIONED` in a PDF `Chunk` — a 3-hop traversal that would require 3 JOINs in SQL and is a single Cypher `MATCH` in Neo4j. Graph traversal queries run in milliseconds at any depth.

### Why a multi-provider LLM fallback chain?

No single LLM provider has 100% uptime. The `get_llm()` factory returns a LangChain `with_fallbacks()` chain: primary call goes to OpenRouter (Gemini 2.0 Flash via `google/gemini-2.0-flash-001`), with automatic fallback to Groq (Llama-3.3-70B) and then Gemini Direct API. A provider outage is transparent to all agents — the graph continues executing with the next available provider.

### Why Cyclic StateGraph instead of simple Chains?

Linear chains (`A → B → C → END`) cannot implement self-correction. LangGraph's `StateGraph` with conditional edges allows loops: `analysis → execution → reflection → execution` (SQL retry), `retrieval → refine → retrieval` (PDF query refinement), `synthesis → verifier → synthesis` (anti-hallucination retry). These cycles are the architectural foundation of agentic reliability.
