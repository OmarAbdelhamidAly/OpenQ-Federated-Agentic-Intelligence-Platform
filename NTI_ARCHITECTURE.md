# 🏛️ Architecture Documentation

**DataAnalyst.AI — Autonomous Enterprise Data Analyst**

---

## Table of Contents

1. [Architectural Principles](#1-architectural-principles)
2. [System Overview](#2-system-overview)
3. [4-Layer Service Architecture](#3-4-layer-service-architecture)
4. [LangGraph Pipeline Deep-Dive](#4-langgraph-pipeline-deep-dive)
5. [Security Architecture](#5-security-architecture)
6. [Data Flow — Full Query Lifecycle](#6-data-flow--full-query-lifecycle)
7. [Database Schema](#7-database-schema)
8. [Infrastructure & Deployment](#8-infrastructure--deployment)
9. [Key Design Decisions](#9-key-design-decisions)

---

## 1. Architectural Principles

**Separation by concern, not by team.**
Each service owns one concept: the API Gateway owns HTTP concerns (auth, routing, validation), the Governance worker owns policy enforcement, the execution pillars own analysis. No service does two jobs.

**Celery queues as the API between layers.**
Services communicate only through named Celery queues over Redis. `api` → `governance` queue → `pillar.sql` queue. No direct HTTP calls between workers. This means a worker crash never blocks the API.

**Stateless workers, stateful checkpointing.**
Every Celery worker is ephemeral — it can be killed and replaced. LangGraph state is persisted to Redis via `AsyncRedisSaver`. A HITL-paused SQL job survives a worker restart.

**Multi-tenant at the data layer, not the application layer.**
A single API deployment serves all tenants. Isolation is enforced by `tenant_id` on every database query — not by separate databases or separate deployments. This is safe because every query is scoped in a SQLAlchemy `where(Model.tenant_id == current_user.tenant_id)` clause.

**Fail loudly in development, fail safely in production.**
The `Settings` validator crashes startup if `SECRET_KEY` or `AES_KEY` are at their default values when `ENV=production`. You cannot accidentally deploy with weak secrets.

---

## 2. System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL WORLD                                   │
│                                                                          │
│  Browser / API client          Groq API (LLM)         Qdrant Cloud       │
│       │                            ▲                       ▲             │
└───────┼────────────────────────────┼───────────────────────┼─────────────┘
        │ HTTPS :8002                │ HTTPS                 │ :6333
┌───────▼────────────────────────────┼───────────────────────┼─────────────┐
│                  DOCKER COMPOSE NETWORK                     │            │
│                                    │                        │            │
│  ┌──────────────────────────────────────────────────────────┐            │
│  │  API GATEWAY  (services/api · :8002)                     │            │
│  │  FastAPI · Async SQLAlchemy · JWT · AES-256              │            │
│  └───────────────────────────┬──────────────────────────────┘            │
│                               │ Celery tasks                              │
│                        ┌──────▼──────┐                                   │
│                        │    REDIS    │ Broker + cache + JWT blacklist     │
│                        └──────┬──────┘                                   │
│           ┌───────────────────┼───────────────────┐                      │
│           ▼                   ▼                   ▼                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐  │
│  │  GOVERNANCE    │  │  WORKER-SQL    │  │  WORKER-CSV / JSON / PDF   │  │
│  │  (Layer 2)     │  │  (Layer 3)     │  │  (Layer 3)                 │  │
│  │  LangGraph:    │  │  LangGraph:    │  │  LangGraph pipelines       │  │
│  │  intake →      │  │  11-node SQL   │  │  per data type             │  │
│  │  guardrail     │  │  pipeline      │  │                            │  │
│  └────────────────┘  └────────────────┘  └────────────────────────────┘  │
│           │                   │                   │                      │
│           └───────────────────┼───────────────────┘                      │
│                               │ export queue                              │
│                        ┌──────▼──────┐                                   │
│                        │  EXPORTER   │ (Layer 4) PDF/XLSX/JSON           │
│                        └─────────────┘                                   │
│                                                                           │
│  ┌─────────────────┐  ┌──────────────────────────────────────────────┐   │
│  │   PostgreSQL    │  │              Shared Volume ./tenants/        │   │
│  │   :5433         │  │  Uploaded files, exported reports            │   │
│  │   Metadata DB   │  └──────────────────────────────────────────────┘   │
│  └─────────────────┘                                                      │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 4-Layer Service Architecture

### Layer 1 — API Gateway (`services/api`)

The only service exposed to the internet. Port 8002.

**What it does:**
- Validates JWT tokens on every protected request
- Enforces tenant scoping on every database query
- Encrypts SQL credentials with AES-256 before storage
- Builds `AnalysisJob` records and dispatches to `governance` queue
- Returns job ID to client immediately (async — never waits for analysis)
- Serves the Glassmorphism SPA at `/`

**What it never does:**
- Executes SQL queries against user databases
- Runs LangGraph agents
- Calls Groq directly

**Internal architecture:**
```
services/api/app/
├── main.py                # FastAPI factory + self-healing DB migration on startup
├── routers/               # auth, users, data_sources, analysis, knowledge,
│                          # policies, metrics, reports
├── models/                # SQLAlchemy ORM: tenant, user, data_source,
│                          # analysis_job, analysis_result, knowledge, policy
├── schemas/               # Pydantic v2 request/response models
├── use_cases/             # Business logic separated from router handlers
│   ├── analysis/          # run_pipeline, diagnose_service
│   ├── auto_analysis/     # Background 5-question generation on upload
│   └── export/            # Export dispatch
└── infrastructure/
    ├── config.py          # Pydantic Settings — crashes on weak prod secrets
    ├── security.py        # JWT + bcrypt
    ├── sql_guard.py       # 3-layer SQL injection guard
    ├── middleware.py      # CORS, rate limit, security headers, request logging
    ├── token_blacklist.py # Redis JTI revocation
    └── adapters/
        ├── encryption.py  # AES-256-GCM
        ├── qdrant.py      # Vector DB adapter
        └── storage.py     # Tenant-scoped file paths
```

---

### Layer 2 — Governance (`services/governance`)

Celery worker on the `governance` queue. Every job passes here first.

**LangGraph graph:**
```
START
  │
  ▼
[intake_agent]
  │  Classifies intent (trend/comparison/ranking/correlation/anomaly)
  │  Extracts entities: table names, column names, date ranges
  │  Detects ambiguity: sets clarification_needed=True if unclear
  │
  ▼
check_intake
  ├── clarification_needed=True → END (job status: "awaiting_clarification")
  └── clear → [guardrail_agent]
                │  Evaluates against admin-defined policies
                │  Detects PII exposure risk
                │  Sets policy_violation=True if blocked
                ▼
               END → dispatches to correct pillar queue
```

The governance layer acts as a **semantic firewall** — it's the only place where admin-defined natural language policies are enforced. A policy like `"never expose salary data"` is evaluated here by the LLM before any query reaches the database.

---

### Layer 3 — Execution Pillars

Four independent Celery workers, each isolated in its own Docker container.

**Queue routing:**
```
source.type = "csv"        → pillar.csv          → worker-csv
source.type = "sql"        → pillar.sql           → worker-sql
source.type = "sqlite"     → pillar.sqlite        → worker-sql
source.type = "postgresql" → pillar.postgresql    → worker-sql
source.type = "json"       → pillar.json          → worker-json
source.type = "document"   → pillar.pdf           → worker-pdf
```

Each pillar has its own `requirements.txt` — the PDF worker has `colpali-engine` and `pypdfium2` while the CSV worker has `pandas` and `scikit-learn`. Workers only install what they need.

---

### Layer 4 — Exporter (`services/exporter`)

Celery worker on the `export` queue. Generates formatted output files from completed `analysis_results` records.

Supported formats: PDF (weasyprint), XLSX (openpyxl), JSON.

Files are written to the shared `tenant_uploads` Docker volume and served via the API gateway.

---

## 4. LangGraph Pipeline Deep-Dive

### SQL Pipeline — 11 Nodes

The centerpiece of the platform. Handles live enterprise databases with schema compression, HITL, self-healing, hybrid knowledge fusion, and quality verification.

#### AnalysisState

The shared state object. Every node reads from it and returns only the fields it modifies:

```python
class AnalysisState(TypedDict):
    question: str           # Original user question
    source_id: str          # Data source identifier
    connection_string: str  # Decrypted at runtime — never stored
    schema_summary: dict    # Compressed table/column metadata from discovery
    generated_sql: str      # SQL query from analysis_generator
    analysis_results: dict  # Query results + execution metadata
    charts: list            # Plotly chart specs from visualization agent
    insight_report: str     # Executive summary from insight agent
    recommendations: list   # Action items from recommendation agent
    reflection_context: str # Self-healing hint on zero-row results
    reflection_count: int   # Max 1 zero-row reflection attempt
    retry_count: int        # Max 3 error retries
    error: str              # Last error message
    policy_violation: str   # Guardrail rejection reason
    approval_granted: bool  # HITL approval flag (Redis checkpointer)
    user_id: str            # "auto_analysis" bypasses HITL
    kb_id: str              # Optional: knowledge base for PDF fusion
    thinking_steps: list    # All node outputs (shown in UI)
```

#### Node Responsibilities

| Node | Responsibility | Self-Healing |
|---|---|---|
| `data_discovery` | Schema compression: parallel table profiling, FK inference, Mermaid ERD generation, `low_cardinality_values` sampling | Handles large schemas via token-budget schema selector |
| `analysis_generator` | ReAct agent: uses `sql_schema_discovery` and golden SQL examples to generate ANSI SELECT | Receives `reflection_context` on retry |
| `human_approval` | Graph interrupt — pauses until `approval_granted=True` in Redis checkpointer | N/A |
| `execution` | Runs approved SQL, fetches up to 1,000 rows, triggers zero-row reflection if needed | Injects case-sensitivity hints for string literal mismatches |
| `backtrack` | Analyzes failure type, generates strategic hint, increments `retry_count` | Routes back to `analysis_generator` (max 3 times) |
| `hybrid_fusion` | Fetches Qdrant KB context related to SQL results | Gracefully skips if `kb_id` is null |
| `visualization` | Generates Plotly chart specs matching the analysis type | Falls back to table view on chart generation failure |
| `insight` | 3-5 sentence executive summary referencing actual data values | — |
| `verifier` | Quality gate: checks insight claims match the data | — |
| `recommendation` | 3 specific, actionable next steps | — |
| `memory_persistence` | Saves successful query+insight to `insight_memory` for golden SQL examples | Fire-and-forget — never blocks pipeline |

#### Zero-Row Reflection (Self-Healing)

The most important self-healing mechanism in the platform:

```
SQL executes → row_count = 0 AND reflection_count < 1
    │
    ▼
Extract string literals from WHERE clauses using regex
Find corresponding column in schema_summary
Check low_cardinality_values for case-insensitive match
    │
    ├── Match found: inject hint
    │   "You filtered by 'active' but sampled data shows 'Active'.
    │    SQL is case-sensitive for string comparisons."
    │
    └── No match: generic hint
        "The query returned 0 rows. Try relaxing the filters."
    │
    ▼
Set reflection_context → route to [backtrack] → [analysis_generator]
    │  Generator receives the hint and rewrites the query
    ▼
Re-execute → typically returns correct results
```

---

### CSV Pipeline — 7 Nodes

```
data_discovery → needs_cleaning? → data_cleaning (optional) → analysis
    → visualization → insight → recommendation → output_assembler
```

**Data quality scoring:**
The discovery agent computes a quality score (0.0–1.0) based on:
- Null ratio: `1 - (total_nulls / total_cells)`
- Type consistency: penalizes mixed-type columns
- Outlier density: penalizes columns where >5% of values are statistical outliers

Scores below 0.9 route through `data_cleaning` before analysis. This prevents the analysis agent from drawing conclusions from dirty data.

**CSV-specific tools:**
- `profile_dataframe` — dtype inference, null counts, unique counts, sample values
- `run_pandas_query` — executes LLM-generated pandas code in a sandboxed eval
- `compute_correlation` — Pearson correlation matrix for numeric columns
- `compute_trend` — time-series decomposition if a date column is detected
- `compute_ranking` — sorted aggregations with percentage contribution
- `clean_dataframe` — null imputation, type coercion, outlier flagging

---

## 5. Security Architecture

### JWT Token Architecture

```
Login
  │  Access token (30 min) — stateless verification via SECRET_KEY
  │  Refresh token (7 days) — JTI stored in Redis
  ▼
Protected API call
  │  Decode JWT, verify signature and expiry
  │  Extract: sub (user_id), tenant_id, role
  ▼
Access token expires
  │  POST /auth/refresh with refresh token
  │  Verify JTI exists in Redis (not revoked)
  │  Revoke old JTI → issue new token pair (rotation)
  ▼
Logout
  │  Delete JTI from Redis
  │  Access token expires naturally — cannot be revoked (stateless)
```

**Why refresh token rotation?** If a refresh token is stolen, it's single-use. The legitimate user's next refresh invalidates the stolen token and issues a new one. The attacker's copy is immediately rejected.

### AES-256 Credential Encryption

```
User provides SQL credentials (host, port, user, password, db)
    │
    ▼
encrypt_json(credentials, AES_KEY)  ← AES-256-GCM, random IV per encryption
    │
    ▼
config_encrypted TEXT column in data_sources
    │
    ▼  At analysis time only:
decrypt_json(config_encrypted, AES_KEY)
    │
    ▼
connection_string injected into AnalysisState (never persisted)
```

The AES key is never stored in the database. Loss of the `AES_KEY` environment variable means all encrypted SQL credentials become permanently unrecoverable.

### SQL Guard — 3 Layers

```python
# Layer 1: Allowlist — only SELECT and CTEs
if not query.upper().startswith(("SELECT", "WITH")):
    raise ValueError("Only SELECT queries are allowed")

# Layer 2: Blocklist — dangerous keywords anywhere in query
DANGEROUS = r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|...)\b"
if re.search(DANGEROUS, query, re.IGNORECASE):
    raise ValueError(f"Forbidden keyword detected: {match.group()}")

# Layer 3: LLM Guardrail (Governance layer)
# Semantic check against admin-defined natural language policies
# e.g. "never expose salary or compensation data"
```

Layer 3 catches what regex can't: semantic policy violations like asking for `compensation` even if the column is named `comp` or `pay`.

### Rate Limiting

Uses `slowapi` (Starlette-compatible SlowAPI):

```
3/minute  — /auth/register   (prevent mass account creation)
5/minute  — /auth/login      (prevent brute-force)
200/minute — all other routes (global default)
```

Key function: `get_remote_address` — limits by IP. In production behind a load balancer, configure `X-Forwarded-For` trust appropriately.

---

## 6. Data Flow — Full Query Lifecycle

```
User: "What are the top 5 products by revenue in Q4?"
  │
  │  POST /api/v1/analysis/query
  ▼
API Gateway
  1. Verify JWT → extract user, tenant, role
  2. Verify data source belongs to tenant
  3. Create AnalysisJob (status=pending) → commit to PostgreSQL
  4. governance_task.apply_async(args=[job_id], queue='governance')
  5. Return {job_id, status="pending"} to client immediately

Redis broker receives task
  │
  ▼
Governance Worker (queue: governance)
  6. Fetch job + data source from PostgreSQL
  7. Decrypt connection string from config_encrypted
  8. intake_agent → classify intent="ranking", extract entities
  9. guardrail_agent → check policies (no violations found)
  10. pillar_task.apply_async(args=[job_id], queue='pillar.sql')

SQL Worker (queue: pillar.sql)
  11. Build LangGraph SQL pipeline with Redis checkpointer
  12. data_discovery_agent → fetch schema, profile 5000 rows
  13. analysis_generator → generate SQL:
      "SELECT product_name, SUM(revenue) AS total
       FROM sales WHERE quarter='Q4'
       GROUP BY product_name ORDER BY total DESC LIMIT 5"
  14. route_after_generator → HITL (user_id != auto_analysis)
  15. Job status updated to "awaiting_approval"
  16. Graph INTERRUPTS at human_approval node
      State saved to Redis checkpointer

Client polls GET /analysis/{job_id}
  Returns: {status="awaiting_approval", generated_sql="SELECT..."}

Admin reviews SQL in UI and clicks Approve
  │
  │  POST /api/v1/analysis/{job_id}/approve
  ▼
API Gateway
  17. Fetch job, verify admin role
  18. Update job status to "running"
  19. Update LangGraph state: {approval_granted: True} via checkpointer
  20. pillar_task.apply_async(args=[job_id], queue='pillar.sql')

SQL Worker resumes from checkpoint
  21. execution node → run SQL against live database
      row_count=5 → no zero-row reflection needed
  22. hybrid_fusion → fetch PDF KB context (kb_id=null → skip)
  23. visualization_agent → generate Plotly bar chart spec
  24. insight_agent → "Product A led Q4 with $2.3M..."
  25. verifier_agent → insight matches data ✓
  26. recommendation_agent → 3 action items
  27. memory_persistence → save to insight_memory
  28. output_assembler → build final result JSON
  29. Save AnalysisResult to PostgreSQL
  30. Update job status to "done"

Client polls GET /analysis/{job_id}
  Returns: {status="done"}

Client fetches GET /analysis/{job_id}/result
  Returns: charts, insight_report, recommendations, data_snapshot
```

---

## 7. Database Schema

**Entity Relationship:**

```
tenants ──< users
        ──< data_sources ──< analysis_jobs ──── analysis_results (1:1)
        ──< knowledge_bases
        ──< policies

analysis_jobs >── knowledge_bases (optional FK for hybrid fusion)
```

**Key design decisions:**

`config_encrypted TEXT` on `data_sources` — credentials are stored as a single encrypted blob rather than individual columns. This means the encryption boundary is clean: either all credential fields are encrypted, or none are.

`thinking_steps JSON` on `analysis_jobs` — every LangGraph node output is captured and stored. This powers the "Reasoning" UI panel that shows users what the agent was thinking, and provides an audit trail for debugging failed jobs.

`auto_analysis_json JSON` on `data_sources` — 5 pre-generated analyses stored permanently on upload. These are computed in the background by the `auto_analysis` service user (bypasses HITL) and displayed immediately when the user opens a data source. First-impression speed matters.

---

## 8. Infrastructure & Deployment

### Docker Compose Stack (9 containers)

```yaml
postgres    # PostgreSQL 16 — metadata database
redis       # Redis Stack — broker + cache + JWT blacklist
qdrant      # Qdrant — vector database for PDF RAG
api         # FastAPI gateway on :8002
governance  # Celery worker — governance queue
worker-sql  # Celery worker — pillar.sql queue
worker-csv  # Celery worker — pillar.csv queue
worker-json # Celery worker — pillar.json queue
worker-pdf  # Celery worker — pillar.pdf queue
exporter    # Celery worker — export queue
```

All workers share the `tenant_uploads` volume for file access. All workers share the same PostgreSQL database via `DATABASE_URL`. Redis is the only inter-service communication channel.

### Kubernetes Production Stack

Production adds:
- **HPA (Horizontal Pod Autoscaler):** scales analysis workers based on queue depth
- **PVC (Persistent Volume Claims):** PostgreSQL and Qdrant data persistence
- **Ingress:** TLS termination + routing
- **Namespace isolation:** all resources in `analyst-ai` namespace
- **Secrets:** Kubernetes Secrets for `GROQ_API_KEY`, `SECRET_KEY`, `AES_KEY`

### Self-Healing Database Migration

The API gateway's `lifespan` runs on every startup:

```python
# 1. Create missing tables (idempotent)
await conn.run_sync(Base.metadata.create_all)

# 2. Add missing columns (idempotent)
await conn.execute("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS generated_sql TEXT NULL")
await conn.execute("ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS thinking_steps JSON NULL")
# ... etc
```

This means adding a new column to a model requires only deploying the new code — no manual migration step, no downtime.

---

## 9. Key Design Decisions

### Why Celery queues between layers instead of HTTP?

HTTP between microservices creates tight coupling — if the governance service is down, analysis submissions fail immediately. Celery queues decouple producers from consumers: the API can accept jobs even when workers are restarting. Workers can be scaled independently by increasing `--concurrency`. Dead-letter queues can catch and retry failed tasks.

### Why one database for all tenants?

Multi-database multi-tenancy (one DB per tenant) scales to thousands of tenants but requires a connection pool of thousands of connections, schema management per tenant, and complex migration orchestration. Single-database with `tenant_id` scoping scales to hundreds of tenants with standard connection pooling and a single migration run. The isolation guarantee is the same — every query is WHERE-scoped. The only risk is a `tenant_id` filter being accidentally omitted, which is why every query goes through a central `get_current_user` dependency that enforces the scope.

### Why Redis checkpointer for HITL?

The HITL pause can last minutes or hours (until an admin approves). A Celery task cannot be "paused" — it must terminate and resume. LangGraph's `AsyncRedisSaver` serializes the full graph state to Redis when `interrupt_before=["human_approval"]` fires. On resume (after approval), the graph is reconstructed from the checkpoint and continues execution from the exact node where it paused. This is what makes HITL durable across worker restarts.

### Why AES-256 for SQL credentials instead of a secrets manager?

A secrets manager (AWS Secrets Manager, HashiCorp Vault) is the right answer for production at scale. AES-256 in the database is a reasonable interim choice for an NTI project: it's production-grade encryption, it's simple to implement and audit, and it has zero external dependencies. The migration path to a secrets manager is straightforward — replace `encrypt_json/decrypt_json` with secrets manager calls.

### Why Qdrant multi-vector (ColPali) for PDFs?

Traditional PDF RAG chunks text and embeds it. ColPali embeds PDF pages as image patches — it preserves visual layout, tables, charts, and diagrams that text extraction destroys. For enterprise documents (financial reports, technical manuals), the layout often carries as much meaning as the text. Multi-vector indexing in Qdrant stores both text embeddings and image patch embeddings per page, enabling queries that find information from charts that have no adjacent text labels.
