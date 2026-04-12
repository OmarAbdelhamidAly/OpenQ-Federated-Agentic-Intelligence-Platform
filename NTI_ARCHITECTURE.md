# 🏛️ Architecture Documentation

**OpenQ — Autonomous Enterprise Data Intelligence Platform**

> An open, composable alternative to Amazon Q Business, built for organizations sitting on fragmented multi-modal data.

---

## Table of Contents

1. [Architectural Principles](#1-architectural-principles)
2. [Clean Architecture per Service](#2-clean-architecture-per-service)
3. [System Overview](#3-system-overview)
4. [4-Layer Service Architecture](#4-4-layer-service-architecture)
5. [LangGraph Pipeline Deep-Dive](#5-langgraph-pipeline-deep-dive)
6. [Security Architecture](#6-security-architecture)
7. [Data Flow — Full Query Lifecycle](#7-data-flow--full-query-lifecycle)
8. [Database Schema](#8-database-schema)
9. [Infrastructure & Deployment](#9-infrastructure--deployment)
10. [Observability Stack](#10-observability-stack)
11. [Key Design Decisions](#11-key-design-decisions)

---

## 1. Architectural Principles

**Separation by concern, not by team.**
Each service owns one concept: the API Gateway owns HTTP concerns (auth, routing, validation), the Governance worker owns policy enforcement, the execution pillars own analysis. No service does two jobs.

**Celery queues as the API between layers.**
Services communicate only through named Celery queues over Redis. `api → governance queue → pillar.sql queue`. No direct HTTP calls between workers. A worker crash never blocks the API — the job stays in the queue until a healthy worker picks it up.

**Stateless workers, stateful checkpointing.**
Every Celery worker is ephemeral. LangGraph state is persisted to Redis via `AsyncRedisSaver`. A HITL-paused SQL job survives a worker restart, a pod eviction, or a full cluster reboot.

**Multi-tenant at the data layer, not the application layer.**
A single API deployment serves all tenants. Isolation is enforced by `tenant_id` on every database query — not by separate databases or deployments. Every query is scoped in a SQLAlchemy `where(Model.tenant_id == current_user.tenant_id)` clause.

**Fail loudly in development, fail safely in production.**
The `Settings` validator crashes startup if `SECRET_KEY` or `AES_KEY` are at their default values when `ENV=production`. You cannot accidentally deploy with weak secrets.

**Observability is not optional.**
Every service emits structured logs via `structlog`. Prometheus metrics are scraped at `/metrics`. Grafana dashboards are provisioned automatically — no manual setup.

**Multi-provider LLM resilience.**
No single LLM vendor is a hard dependency. The LLM factory implements a fallback chain: `OpenRouter (Gemini 2.0 Flash) → Groq (Llama-3.3-70B) → Gemini Direct API`. A provider outage degrades gracefully without data loss.

---

## 2. Clean Architecture per Service

Every microservice (API, governance, worker-sql, worker-csv, worker-json, worker-pdf) follows the same **Clean (Hexagonal) Architecture** layout, enforcing the Dependency Inversion Principle:

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
│       └── tools/             ← Langchain Tools wrapping external calls
│
├── infrastructure/            ← Frameworks & Drivers (outermost ring)
│   ├── config.py              ← Pydantic Settings — reads env vars, validates on startup
│   ├── database/postgres.py   ← SQLAlchemy async engine + session factory
│   ├── llm.py                 ← LLM factory: OpenRouter → Groq → Gemini fallback chain
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
┌──────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL WORLD                                   │
│                                                                          │
│  Browser / API client   OpenRouter / Gemini 2.0 Flash   Qdrant Cloud     │
│       │                         ▲                            ▲           │
└───────┼─────────────────────────┼────────────────────────────┼───────────┘
        │ HTTPS :8002             │ HTTPS                      │ :6333
┌───────▼─────────────────────────┼────────────────────────────┼───────────┐
│                  DOCKER COMPOSE NETWORK                       │           │
│                                 │                             │           │
│  ┌────────────────────────────────────────────────────────────┐           │
│  │  API GATEWAY  (services/api · :8002)                       │           │
│  │  FastAPI · Async SQLAlchemy · JWT · AES-256-GCM            │           │
│  └───────────────────────────┬────────────────────────────────┘           │
│                               │ Celery tasks via Redis broker             │
│                        ┌──────▼──────┐                                   │
│                        │    REDIS    │ Broker + result backend            │
│                        │             │ + JWT JTI blacklist                │
│                        │             │ + LangGraph HITL checkpoints       │
│                        └──────┬──────┘                                   │
│           ┌───────────────────┼────────────────────┐                     │
│           ▼                   ▼                    ▼                     │
│  ┌────────────────┐  ┌──────────────┐  ┌───────────────────────────────┐ │
│  │  GOVERNANCE    │  │  WORKER-SQL  │  │  WORKER-CSV / JSON / PDF      │ │
│  │  (Layer 2)     │  │  (Layer 3)   │  │  (Layer 3)                    │ │
│  │  2-node graph  │  │  12-node     │  │  CSV: 11 nodes                │ │
│  │  intake →      │  │  Cyclic      │  │  JSON: 10 nodes               │ │
│  │  guardrail     │  │  StateGraph  │  │  PDF: 10 nodes (Orchestrator) │ │
│  └────────────────┘  └──────────────┘  └───────────────────────────────┘ │
│           │                   │                    │                     │
│           └───────────────────┼────────────────────┘                     │
│                               │ export queue                             │
│                        ┌──────▼──────┐                                   │
│                        │  EXPORTER   │ (Layer 4) PDF/XLSX/JSON           │
│                        └─────────────┘                                   │
│                                                                           │
│  ┌──────────────┐  ┌────────────┐  ┌───────────────────────────────────┐  │
│  │  PostgreSQL  │  │   Qdrant   │  │     Shared Volume ./tenants/      │  │
│  │  :5433       │  │   :6333    │  │  Uploaded files · Exported reports│  │
│  │  Metadata DB │  │  JSON RAG  │  └───────────────────────────────────┘  │
│  └──────────────┘  └────────────┘                                         │
│                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐                                │
│  │   Prometheus    │  │     Grafana     │ Observability stack            │
│  │   :9090         │  │     :3000       │                                │
│  └─────────────────┘  └─────────────────┘                                │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 4-Layer Service Architecture

### Layer 1 — API Gateway (`services/api`)

The only public-facing service. Handles HTTP, auth, file storage, and Celery dispatch. Never executes analysis logic directly.

**Routing table:**

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
| `/voice/*` | Voice-to-text query submission |
| `/superset/*` | Apache Superset embedded analytics proxy |

**Key infrastructure modules:**

```
infrastructure/
├── config.py           Pydantic Settings — validates env vars on startup
├── security.py         JWT access (30min) + refresh (7 days) + bcrypt
├── sql_guard.py        3-layer SQL injection prevention
├── middleware.py       CORS · rate limiting (slowapi) · security headers
├── token_blacklist.py  Redis-backed JTI revocation set
├── llm.py              Multi-provider factory: OpenRouter → Groq → Gemini
└── adapters/
    ├── encryption.py   AES-256-GCM — encrypt/decrypt SQL connection strings
    ├── qdrant.py       Async Qdrant client — multi-vector upsert + search
    └── storage.py      Tenant-scoped file path resolution
```

**Self-healing startup:** The `lifespan` context manager acquires a PostgreSQL advisory lock, then runs idempotent `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every deploy. Lock timeout is 5s per statement to prevent startup hangs on a loaded database.

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
- Extract named entities (table names, column names, date ranges)
- Detect ambiguous or underspecified questions
- Assign complexity index (1–5) based on entity count and join requirements

**Guardrail Agent responsibilities:**
- Load active policies for the tenant from PostgreSQL
- LLM semantic check: does this question violate any policy?
- PII detection: would the answer expose sensitive columns?
- If violation: set job to `error` status with a human-readable explanation

The bypass path: `auto_analysis` system user (`user_id == "auto_analysis"`) skips governance — background analyses triggered on upload are system-generated and policy-safe by construction.

---

### Layer 3 — Execution Pillars

Four independently scalable Celery workers:

```
worker-sql   → queues: pillar.sql, pillar.sqlite, pillar.postgresql
worker-csv   → queue:  pillar.csv
worker-json  → queue:  pillar.json
worker-pdf   → queue:  pillar.pdf
worker-code  → queue:  pillar.code
worker-nexus → queue:  pillar.nexus
worker-audio/image/video → queue: pillar.audio / pillar.image / pillar.video
```

Each worker is a separate Docker container with its own `requirements.txt`. The SQL worker can scale to 10 replicas without affecting CSV or PDF processing.

All workers share the same **Clean Architecture layout** and the same **`AnalysisState` TypedDict** (defined in `domain/analysis/entities.py`) as the LangGraph state schema.

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
                                        [insight]        ← 3–5 sentence executive summary
                                             │              Grounded in actual row values + kb_context
                                             ▼
                                        [verifier]       ← Quality gate: insight vs data
                                             │              Prevents hallucinated insights
                                             ▼
                                    [recommendation]     ← 3 actionable next steps
                                             ▼
                                      [save_cache]       ← Saves {question → result} to semantic cache
                                             │              Enables fast retrieval of similar future queries
                                             ▼
                                   [output_assembler]    ← Builds final JSON envelope
                                             │              Writes AnalysisResult to PostgreSQL
                                             │              Updates job status → "done"
                                             ▼
                                            END
```

**Self-healing mechanisms:**
- **Zero-Row Reflection:** `row_count=0` triggers `reflection_context` injection. The reflection agent analyzes the SQL, compares literals against `low_cardinality_values`, detects case mismatches, and injects a corrective hint. Max 3 retries.
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
  ├── error + retry < 3 → [reflection]  ← Repairs Python code errors, increments retry_count
  │                            └──► [analysis]  (retry loop)
  └── success → [visualization]  ← Plotly/ECharts chart spec
                      │
                      ▼
                 [insight]         ← Executive summary grounded in computed statistics
                      ▼
                 [verifier]        ← Quality gate
                      ▼
               [recommendation]   ← 3 next steps based on statistical findings
                      ▼
           [output_assembler]     ← Final JSON → PostgreSQL write
                      ▼
              [save_cache]        ← Semantic cache save → END
```

---

### JSON Pipeline — 10 Nodes (Directed Cyclic StateGraph)

Backed by **MongoDB** for document intelligence over semi-structured JSON stores, with **Qdrant** for semantic decomposition and vector search.

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

The most architecturally complex pipeline. A master orchestrator routes between **three specialist synthesis engines** based on document type and retrieval quality.

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

           [vision_synthesis]    ← Gemini 2.0 Flash Vision: PDF pages rendered as images,
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

### OCR Synthesis (Part of PDF Pipeline)
This node does specialized PaddleOCR extraction.

---

### Codebase Pipeline — 8 Nodes (Cyclic StateGraph)

A specialized pipeline analyzing full source code repositories mapped into an Abstract Syntax Tree (AST) in Neo4j.

```
START
  │
  ▼
[data_discovery]     ← Neo4j APOC connection. Discovers graph schema,
  │                     labels (Class, Function, File), and relationships
  ▼
[guardrail]          ← Policy enforcement for source code queries
  ▼
[cypher_generator]   ← ReAct agent natively writing Cypher queries
  │                     against the Neo4j schema
  │
check_cypher_result
  ├── error + retry < 3 → [reflection]  ← Repairs invalid Cypher syntax
  │                            └──► [cypher_generator]
  └── success → [insight]
                    ▼
               [verifier]
                    ▼
           [memory_manager]    ← Episodic memory: updates conversational running summary
                    ▼
          [output_assembler]
                    ▼
             [save_cache] → END
```

---

### Nexus Strategic Pipeline — 6 Nodes (Federated Orchestrator)

The ultimate federator. Triggers and consolidates queries across SQL, CSV, JSON, PDF, and Code pillars.

```
START
  │
  ▼
[nexus_router]       ← Determines which underlying pillars (workers) can
  │                     answer fractions of the strategic query
  ▼
[graph_explorer]     ← Spawns async Celery tasks to `pillar.sql`, `pillar.code`, etc.
  │                     Waits for distributed results (Scatter-Gather pattern)
  ▼
[synthesis_engine]   ← Ultimate synthesis of cross-domain structured and unstructured data
  ▼
[memory_manager]     ← Global organizational memory
  ▼
[verifier]           ← Strategic hallucination check
  ▼
[output_assembler]
  ▼
[save_cache] → END
```

---

### Governance Pipeline — 2 Nodes

```
START → [intake_agent] → check_intake → [guardrail_agent] → route_to_pillar → END
                               │
                               └── clarification_needed → END
```

---

## 6. Security Architecture

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
      └── Token is permanently dead — even if someone captured it, it's worthless
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

The `AES_KEY` env var is the only key material. Loss of the key = permanent loss of all encrypted SQL credentials by design.

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

## 7. Data Flow — Full Query Lifecycle

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
  7. Decrypt config_encrypted → connection_string (in memory only)
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
  15. graph state serialized to Redis via AsyncRedisSaver
  16. Job status → "awaiting_approval". Worker exits cleanly.

Client polls GET /analysis/{job_id}
  ← { status: "awaiting_approval", generated_sql: "SELECT p.name..." }

Admin reviews SQL in UI. Clicks "Approve".
  │
  │  POST /api/v1/analysis/{job_id}/approve
  ▼
API Gateway
  17. Verify admin role
  18. Update job status → "running"
  19. Patch LangGraph state in Redis: { approval_granted: True }
  20. pillar_task.apply_async(args=[job_id], queue="pillar.sql")

SQL Worker resumes from Redis checkpoint
  21. [execution] → runs approved SQL → row_count=5
  22. [hybrid_fusion] → kb_id=null → skip Qdrant
  23. [visualization] → ECharts bar chart: products vs revenue
  24. [insight] → "Product A led Q4 with $2.3M, 28% of quarterly total..."
  25. [verifier] → insight references row values ✓
  26. [recommendation] → ["Prioritize Product A inventory...", ...]
  27. [save_cache] → saves question+result to semantic cache (Redis/Qdrant)
  28. [output_assembler] → build AnalysisResult JSON
  29. INSERT AnalysisResult → UPDATE job status → "done"

Client polls GET /analysis/{job_id} ← { status: "done" }
Client fetches GET /analysis/{job_id}/result
  ← { charts, insight_report, recommendations, data_snapshot }
```

Total time (typical): 8–18 seconds from query submission to result, excluding HITL pause.

---

## 8. Database Schema

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

---

## 9. Infrastructure & Deployment

### Docker Compose — 12 Services

```yaml
services:
  postgres:      # PostgreSQL 16 — metadata database
  redis:         # Redis Stack — broker + cache + JWT blacklist + HITL checkpoints
  qdrant:        # Qdrant — vector database for JSON RAG
  api:           # FastAPI gateway :8002 + static SPA
  governance:    # Celery worker — governance queue
  worker-sql:    # Celery worker — pillar.sql/.sqlite/.postgresql queues
  worker-csv:    # Celery worker — pillar.csv queue
  worker-json:   # Celery worker — pillar.json queue
  worker-pdf:    # Celery worker — pillar.pdf queue
  exporter:      # Celery worker — export queue
  prometheus:    # Metrics collection :9090
  grafana:       # Dashboards :3000
```

All workers share `tenant_uploads` volume for file access. Redis is the only inter-service communication channel.

### Kubernetes — Production

- **HPA:** analysis workers auto-scale based on Celery queue depth (custom metric via Prometheus adapter)
- **PVC:** PostgreSQL and Qdrant data persistence across pod restarts
- **Ingress:** TLS termination + path routing
- **Namespace:** all resources in `analyst-ai` namespace
- **Secrets:** Kubernetes Secrets for `GEMINI_API_KEY`, `GROQ_API_KEY`, `SECRET_KEY`, `AES_KEY`

### Self-Healing Database Migration

On every startup, the API acquires a PostgreSQL advisory lock and runs:
1. `Base.metadata.create_all` — creates missing tables (idempotent)
2. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — adds new columns individually
3. FK constraint checks via `DO $$ BEGIN ... EXCEPTION WHEN ...` blocks

Adding a new column requires only deploying new code — no migration script, no downtime.

---

## 10. Observability Stack

### Prometheus

Scrapes metrics from API Gateway at `/metrics`:

```
OpenQ_api_requests_total{method, endpoint, status_code}
OpenQ_api_request_duration_seconds{method, endpoint}
OpenQ_jobs_total{status, intent, source_type}
OpenQ_jobs_duration_seconds{pipeline, node}
OpenQ_queue_depth{queue_name}
```

### Grafana

Pre-provisioned dashboards (no manual setup):

| Dashboard | Key Panels |
|---|---|
| **Platform Overview** | Active jobs, error rate, p50/p95/p99 latency, queue depths |
| **Pipeline Performance** | Per-node latency breakdown across all 4 worker pipelines |
| **Tenant Analytics** | Jobs per tenant, data source distribution, intent breakdown |
| **Security** | Rate limit hits, auth failures, JWT revocations |

Access: `http://localhost:3000` — admin/admin (change in production).

### Structured Logging

All services emit JSON logs via `structlog` with automatic context variable binding (job_id bound at task start):

```json
{
  "timestamp": "2026-03-20T09:05:12.334Z",
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

## 11. Key Design Decisions

### Why Clean Architecture per service?

Each microservice could be a simple script. Instead, we applied the Dependency Inversion Principle: `domain/` and `use_cases/` layers import nothing from `infrastructure/`. This means swapping Groq for Gemini, or switching from Redis to PostgreSQL as the LangGraph checkpointer, requires changes only in the outermost ring. Core agent logic (the expensive-to-test, expensive-to-reason-about part) is isolated from framework churn.

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

### Why a multi-provider LLM fallback chain?

No single LLM provider has 100% uptime. The `get_llm()` factory returns a LangChain `with_fallbacks()` chain: primary call goes to OpenRouter (Gemini 2.0 Flash via `google/gemini-2.0-flash-001`), with automatic fallback to Groq (Llama-3.3-70B) and then Gemini Direct API. A provider outage is transparent to all agents — the graph continues executing with the next available provider.

### Why Cyclic StateGraph instead of simple Chains?

Linear chains (`A → B → C → END`) cannot implement self-correction. LangGraph's `StateGraph` with conditional edges allows loops: `analysis → execution → reflection → execution` (SQL retry), `retrieval → refine → retrieval` (PDF query refinement), `synthesis → verifier → synthesis` (anti-hallucination retry). These cycles are the architectural foundation of agentic reliability.
