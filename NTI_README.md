<div align="center">

# 🤖 DataAnalyst.AI

**Autonomous Enterprise Data Analyst — Multi-Tenant SaaS Platform**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Queue%20%2B%20Cache-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose%20%2B%20K8s-2496ED?logo=docker&logoColor=white)](https://docker.com)

<br/>

*Connect your CSV, SQL database, JSON, or PDF. Ask a question in plain English. Get back a fully reasoned, chart-backed, cited insight — automatically.*

</div>

---

## 📋 Table of Contents

1. [What It Does](#-what-it-does)
2. [System Architecture](#-system-architecture)
3. [Repository Structure](#-repository-structure)
4. [Services Deep-Dive](#-services-deep-dive)
5. [LangGraph Pipelines](#-langgraph-pipelines)
6. [Security Architecture](#-security-architecture)
7. [Database Schema](#-database-schema)
8. [Deployment](#-deployment)
9. [Getting Started](#-getting-started)
10. [Configuration](#-configuration)
11. [Tech Stack](#-tech-stack)

---

## 🎯 What It Does

DataAnalyst.AI is a **multi-tenant SaaS platform** that turns raw data into executive-grade insights through an autonomous multi-agent pipeline. Users connect a data source, ask a natural-language question, and the system handles everything else — schema discovery, query generation, self-healing on failure, visualization, insight synthesis, and export.

**Supported data sources:**
- **CSV / XLSX / SQLite** — upload flat files, get instant analysis
- **PostgreSQL / MySQL** — connect enterprise databases via encrypted credentials
- **JSON** — structured event or log data
- **PDF** — unstructured documents via Qdrant vector search

**What makes it different:**
- **Zero-Row Reflection** — if a SQL query returns empty results, the agent detects the failure, analyzes the data distribution, and rewrites the query automatically
- **Human-in-the-Loop (HITL)** — SQL queries pause for admin approval before execution against live databases
- **Hybrid Fusion** — SQL results are enriched with context from a linked PDF knowledge base
- **3-Layer Security Guardrails** — `EXPLAIN`-cost analysis, strict regex injection prevention, and LLM-based policy enforcement
- **Multi-Tenant Isolation** — every tenant's data, credentials, and jobs are fully isolated at the database level

---

## 🏗️ System Architecture

The platform is built as a **4-layer microservices stack** orchestrated by Docker Compose (and Kubernetes for production):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           END USER / ADMIN                              │
│                    Glassmorphism SPA (Vanilla JS + Plotly.js)           │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTPS
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 1 — API GATEWAY  (services/api  · FastAPI · :8002)               │
│                                                                          │
│  Auth (JWT + refresh rotation)  · Rate limiting · Security headers      │
│  Multi-tenant routing · AES-256 credential encryption · REST endpoints  │
│  Celery task dispatch → Redis broker                                    │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Celery tasks via Redis
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 2 — GOVERNANCE  (services/governance · Celery worker)            │
│                                                                          │
│  Intake Agent — parse intent, extract entities, check ambiguity         │
│  Guardrail Agent — LLM-based policy enforcement, PII detection          │
│  Routes to appropriate pillar or requests clarification                 │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Celery tasks by type
         ┌─────────────────────────┼──────────────────────────┐
         ▼                         ▼                          ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────┐
│  LAYER 3        │   │  LAYER 3        │   │  LAYER 3                │
│  worker-sql     │   │  worker-csv     │   │  worker-json            │
│  worker-pdf     │   │                 │   │                         │
│                 │   │ LangGraph CSV   │   │ LangGraph JSON          │
│ LangGraph SQL   │   │ Pipeline:       │   │ Pipeline                │
│ Pipeline:       │   │ discovery →     │   │                         │
│ discovery →     │   │ [clean?] →      │   └─────────────────────────┘
│ generator →     │   │ analysis →      │
│ [HITL pause] →  │   │ visualization → │
│ execution →     │   │ insight →       │
│ [reflect?] →    │   │ recommendation  │
│ fusion →        │   │                 │
│ insight →       │   └─────────────────┘
│ verifier →      │
│ recommendation  │
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — EXPORTER  (services/exporter · Celery worker)               │
│                                                                          │
│  PDF / XLSX / JSON export · Async generation · Tenant-scoped storage   │
└─────────────────────────────────────────────────────────────────────────┘

SHARED INFRASTRUCTURE
─────────────────────────────────────────────────────────────────────────
PostgreSQL :5433  — Metadata: tenants, users, jobs, results, policies
Redis :6379       — Celery broker + result backend + JWT token blacklist
Qdrant :6333      — Vector DB for PDF knowledge base (multi-vector ColPali)
```

---

## 📂 Repository Structure

```
NTI-grad-project/
│
├── 📁 services/
│   ├── api/                      # Layer 1: Public API Gateway
│   │   └── app/
│   │       ├── main.py           # FastAPI app factory + self-healing DB migration
│   │       ├── routers/          # auth · users · data_sources · analysis
│   │       │                     # knowledge · policies · metrics · reports
│   │       ├── models/           # SQLAlchemy: tenant · user · data_source
│   │       │                     # analysis_job · analysis_result · knowledge · policy
│   │       ├── schemas/          # Pydantic request/response schemas
│   │       ├── use_cases/        # Business logic: run_pipeline · auto_analysis · export
│   │       ├── infrastructure/
│   │       │   ├── config.py     # Pydantic Settings — all config from env vars
│   │       │   ├── security.py   # JWT access/refresh tokens + bcrypt password hashing
│   │       │   ├── sql_guard.py  # 3-layer SQL injection prevention
│   │       │   ├── middleware.py # CORS · rate limiting · security headers · logging
│   │       │   ├── token_blacklist.py # Redis-backed JWT revocation
│   │       │   └── adapters/
│   │       │       ├── encryption.py  # AES-256 for SQL credentials at rest
│   │       │       ├── qdrant.py      # Vector DB adapter
│   │       │       └── storage.py     # Tenant-scoped file storage
│   │       ├── modules/shared/agents/ # Shared: intake · guardrail · output_assembler
│   │       └── static/           # Glassmorphism SPA (HTML + CSS + JS)
│   │
│   ├── governance/               # Layer 2: Policy + Guardrail worker
│   │   └── app/modules/governance/
│   │       ├── workflow.py       # LangGraph: intake → [clarify?] → guardrail
│   │       └── agents/           # intake_agent · guardrail_agent
│   │
│   ├── worker-sql/               # Layer 3: SQL analysis pipeline
│   │   └── app/modules/sql/
│   │       ├── workflow.py       # LangGraph SQL graph (11 nodes)
│   │       ├── agents/           # data_discovery · analysis · visualization
│   │       │                     # insight · verifier · recommendation
│   │       ├── tools/            # run_sql_query · sql_schema_discovery
│   │       └── utils/            # golden_sql · insight_memory · schema_mapper
│   │                             # schema_selector · sql_validator
│   │
│   ├── worker-csv/               # Layer 3: CSV/flat-file analysis pipeline
│   │   └── app/modules/csv/
│   │       ├── workflow.py       # LangGraph CSV graph (7 nodes)
│   │       ├── agents/           # data_discovery · data_cleaning · analysis
│   │       │                     # visualization · insight · recommendation
│   │       └── tools/            # clean_dataframe · compute_correlation
│   │                             # compute_ranking · compute_trend · profile_dataframe
│   │
│   ├── worker-json/              # Layer 3: JSON analysis pipeline
│   ├── worker-pdf/               # Layer 3: PDF RAG pipeline (ColPali multi-vector)
│   └── exporter/                 # Layer 4: Async export service
│
├── 📁 k8s/                       # Kubernetes manifests (production)
│   ├── namespace.yaml
│   ├── api-deployment.yaml
│   ├── worker-deployment.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-deployment.yaml
│   ├── hpa.yaml                  # Horizontal Pod Autoscaler
│   ├── ingress.yaml
│   ├── pvc.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
│
├── 📁 tests/                     # Test suite
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_data_sources.py
│   ├── test_analysis.py (csv + sql pipelines)
│   ├── test_health.py
│   └── test_architecture.py
│
├── 📁 alembic/                   # Database migrations
│   └── versions/                 # 001_initial · add_auto_analysis_fields
│
├── docker-compose.yml            # 9-service local stack
├── .env.example                  # All required environment variables
├── SQL_TEAM.md                   # SQL pipeline engineering guide
├── CSV_TEAM.md                   # CSV pipeline engineering guide
├── DEPLOYMENT.md                 # Docker + Kubernetes deployment guide
└── ADMIN_GUIDE.md                # Platform administration reference
```

---

## 🔧 Services Deep-Dive

### Layer 1 — API Gateway (`services/api`)

The single public entry point for all client requests. Never executes analysis directly — it validates, persists, and dispatches.

**Key responsibilities:**

| Module | Role |
|---|---|
| `routers/auth.py` | Register, login, refresh, logout with JWT rotation and Redis revocation |
| `routers/data_sources.py` | Upload CSV/XLSX/SQLite, connect SQL via AES-256 encrypted credentials, auto-profile schema |
| `routers/analysis.py` | Submit queries, poll job status, fetch results, approve HITL jobs |
| `routers/knowledge.py` | Upload PDFs → Qdrant multi-vector indexing for hybrid SQL+PDF fusion |
| `routers/policies.py` | Admin-managed guardrail rules (e.g. "never expose PII columns") |
| `routers/metrics.py` | Job analytics, latency tracking, tenant usage stats |
| `routers/reports.py` | Export results as PDF/XLSX/JSON (dispatched to exporter worker) |
| `infrastructure/security.py` | JWT access (30min) + refresh (7 days) tokens, bcrypt passwords, JTI-based revocation |
| `infrastructure/sql_guard.py` | 3-layer read-only enforcement: regex + keyword + EXPLAIN cost |
| `infrastructure/middleware.py` | CORS, rate limiting (200/min global, 5/min login, 3/min register), security headers |
| `infrastructure/adapters/encryption.py` | AES-256 GCM encryption for SQL connection strings stored in DB |

**Multi-tenant isolation:** every database query is scoped by `tenant_id`. A user from tenant A cannot see, modify, or even detect the existence of tenant B's data sources, jobs, or results.

**Self-healing startup:** the `lifespan` context manager runs `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every startup — safe to redeploy with zero downtime.

---

### Layer 2 — Governance (`services/governance`)

A dedicated Celery worker on the `governance` queue. Every analysis job passes through here first before reaching any execution pillar.

**LangGraph flow:**
```
START → [intake] → check_intake → [guardrail] → END
                        │
                        └── clarification_needed → END (asks user)
```

- **Intake Agent:** Classifies intent (`trend | comparison | ranking | correlation | anomaly`), extracts entities, detects ambiguous questions
- **Guardrail Agent:** Enforces admin-defined policies, checks for PII exposure, validates the question is safe to execute

If intake detects ambiguity, the job is halted and the user is asked to rephrase. If guardrail flags a policy violation, the job is rejected with a human-readable explanation.

---

### Layer 3 — Execution Pillars

Four specialized Celery workers, each on its own queue:

| Worker | Queue | Concurrency | Pipeline |
|---|---|---|---|
| `worker-sql` | `pillar.sql, pillar.sqlite, pillar.postgresql` | 4 | 11-node LangGraph SQL graph |
| `worker-csv` | `pillar.csv` | 4 | 7-node LangGraph CSV graph |
| `worker-json` | `pillar.json` | 4 | JSON analysis pipeline |
| `worker-pdf` | `pillar.pdf` | 4 | ColPali multi-vector RAG |

Each worker is a completely independent Docker container with its own `requirements.txt` — the SQL worker can scale to 10 replicas without affecting CSV processing.

---

### Layer 4 — Exporter (`services/exporter`)

Async export worker on the `export` queue. Generates PDF/XLSX/JSON reports from completed analysis results. Results are written to the shared `tenant_uploads` volume and served via signed download URLs.

---

## 🔄 LangGraph Pipelines

### SQL Pipeline (11 nodes)

The most complex pipeline in the system. Handles enterprise databases with schema discovery, HITL approval, self-healing, hybrid knowledge base fusion, and quality verification.

```
START
  │
  ▼
[data_discovery]
  │  Schema mapper: tables, columns, PKs, FKs, sample values, low-cardinality enums
  │  Parallel table profiling · Mermaid ERD generation · Schema compression
  ▼
[analysis_generator]  ← ReAct agent with golden SQL examples
  │  Generates ANSI SELECT query + execution plan
  │  Tools: sql_schema_discovery, run_sql_query (dry-run mode)
  ▼
route_after_generator
  ├── approval_granted=True OR auto_analysis → [execution]
  └── default → [human_approval]  ← HITL INTERRUPT (Redis checkpointer)
                      │
                      ▼ admin clicks "Approve" in UI
                 [execution]
                      │  Runs approved SQL, fetches up to 1,000 rows
                      │
                      ▼ Zero-Row Reflection
                 route_after_execution
                  ├── reflection_context → [backtrack]
                  │       │  Analyzes failure, adds case-sensitivity hint
                  │       └──► [analysis_generator]  (retry loop, max 3)
                  └── success → [hybrid_fusion]
                                    │  Fetches PDF knowledge base context
                                    │  related to SQL results (Qdrant)
                                    ▼
                              [visualization]  → Plotly chart JSON
                                    ▼
                               [insight]       → 3-5 sentence executive summary
                                    ▼
                               [verifier]      → Quality gate: checks insight
                                    ▼           matches the data
                            [recommendation]   → 3 actionable next steps
                                    ▼
                          [memory_persistence] → Saves to insight_memory for
                                    ▼           future golden SQL examples
                          [output_assembler]   → Final JSON output
                                    ▼
                                   END
```

**Self-healing mechanisms:**
- **Zero-Row Reflection:** detects `row_count=0`, extracts SQL literals, compares against sampled `low_cardinality_values` for case mismatches, injects a correction hint into the next generation cycle
- **Backtrack Node:** on any error or policy violation, adds a strategic hint and routes back to `analysis_generator` (max 3 retries)
- **Verifier Agent:** quality control gate between insight and recommendation — ensures the insight is actually supported by the data

---

### CSV Pipeline (7 nodes)

Simpler than SQL — no HITL needed since CSVs are user-uploaded files with no sensitive database credentials.

```
START
  │
  ▼
[data_discovery]   → Profile DataFrame: dtypes, nulls, uniques, sample values
  │
  ▼
needs_cleaning (data_quality_score < 0.9?)
  ├── YES → [data_cleaning]  → Handle nulls, type coercion, outlier flagging
  │              └──► [analysis]
  └── NO  →              [analysis]  → Pandas query + statistical analysis
                              ▼
                        [visualization]   → Plotly chart JSON
                              ▼
                          [insight]       → Executive summary
                              ▼
                       [recommendation]   → Next steps
                              ▼
                      [output_assembler]  → Final JSON
                              ▼
                             END
```

**Data quality routing:** the discovery agent computes a quality score based on null ratio, type consistency, and outlier density. Scores below 0.9 trigger automatic cleaning before analysis proceeds.

---

### Governance Pipeline (2 nodes)

```
START → [intake] → check_intake → [guardrail] → END
                        └── clarification_needed → END
```

Runs before every analysis job regardless of data source type. The only way to bypass governance is the `auto_analysis` system user (background jobs triggered on data source upload).

---

## 🔒 Security Architecture

### Authentication — JWT with Rotation

```
Register / Login
    │  POST /api/v1/auth/login
    │  Returns: access_token (30min) + refresh_token (7 days)
    ▼
Protected Request
    │  Authorization: Bearer {access_token}
    ▼
Access Token Expired?
    │  POST /api/v1/auth/refresh {refresh_token}
    │  OLD refresh token → REVOKED (JTI deleted from Redis)
    │  NEW refresh token issued
    ▼
Logout
    │  POST /api/v1/auth/logout {refresh_token}
    │  JTI added to Redis blacklist — token is dead even before expiry
```

### SQL Injection Prevention (3 Layers)

```
Layer 1 — Regex guard (sql_guard.py)
    Pattern: \b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|...)\b
    Applied to ALL SQL before any database connection
    Raises ValueError on any match

Layer 2 — SELECT-only enforcement
    Query must start with SELECT or WITH (CTEs allowed)
    Applied before Layer 1 keyword scan

Layer 3 — LLM Guardrail Agent
    Policy-aware: admin can add rules like "never query salary columns"
    Checks semantic intent, not just syntax
```

### AES-256 Credential Encryption

SQL connection strings (host, port, username, password, database) are serialized to JSON and encrypted with AES-256-GCM before storage. The encryption key is never stored in the database — it lives exclusively in the `AES_KEY` environment variable. If the env var is lost, credentials are permanently unrecoverable.

### Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /api/v1/auth/register` | 3 requests / minute |
| `POST /api/v1/auth/login` | 5 requests / minute |
| All other endpoints | 200 requests / minute |

### Security Headers (every response)

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cache-Control: no-store  (API routes only)
```

---

## 🗄️ Database Schema

```
tenants
├── id UUID PK
├── name TEXT
├── plan VARCHAR(50)   "internal" | "pro" | "enterprise"
└── created_at TIMESTAMPTZ

users
├── id UUID PK
├── tenant_id UUID FK → tenants
├── email TEXT UNIQUE
├── password_hash TEXT
├── role VARCHAR(10)   "admin" | "viewer"
├── created_at TIMESTAMPTZ
└── last_login TIMESTAMPTZ

data_sources
├── id UUID PK
├── tenant_id UUID FK → tenants
├── type VARCHAR(10)         "csv" | "sql" | "document"
├── name TEXT
├── file_path TEXT           CSV: /tmp/tenants/{tenant_id}/file.csv
├── config_encrypted TEXT    SQL: AES-256 encrypted connection JSON
├── schema_json JSON         columns, types, row count, sample values
├── auto_analysis_status VARCHAR(10)  "pending"|"running"|"done"|"failed"
├── auto_analysis_json JSON  5 pre-generated analyses (on upload)
├── domain_type VARCHAR(30)  "sales"|"hr"|"finance"|"inventory"|"customer"
└── created_at TIMESTAMPTZ

analysis_jobs
├── id UUID PK
├── tenant_id UUID FK → tenants
├── user_id UUID FK → users
├── source_id UUID FK → data_sources
├── question TEXT
├── intent VARCHAR(50)       "trend"|"comparison"|"ranking"|"correlation"|"anomaly"
├── status VARCHAR(20)       "pending"|"running"|"done"|"error"|"awaiting_approval"
├── generated_sql TEXT       SQL query (shown to user before HITL approval)
├── thinking_steps JSON      LangGraph node outputs for UI reasoning display
├── complexity_index INTEGER  1-5 scale from intake agent
├── total_pills INTEGER       number of analysis sub-questions
├── retry_count INTEGER
├── kb_id UUID FK → knowledge_bases  (optional PDF fusion)
├── started_at TIMESTAMPTZ
├── completed_at TIMESTAMPTZ
└── error_message TEXT

analysis_results
├── id UUID PK
├── job_id UUID FK → analysis_jobs (unique)
├── charts JSON         array of Plotly chart specs
├── insight_report TEXT executive summary
├── recommendations JSON array of action items
├── data_snapshot JSON  first 100 rows of query result
└── embedding JSON      result embedding for similarity search

knowledge_bases
├── id UUID PK
├── tenant_id UUID FK → tenants
├── name TEXT
├── description TEXT
└── created_at TIMESTAMPTZ

policies
├── id UUID PK
├── tenant_id UUID FK → tenants
├── name TEXT
├── rule TEXT            natural language policy rule
├── is_active BOOLEAN
└── created_at TIMESTAMPTZ
```

---

## 🚀 Deployment

### Docker Compose (Local / Staging)

```bash
# 1. Clone and configure
git clone https://github.com/OmarAbdelhamidAly/NTI-grad-project.git
cd NTI-grad-project
cp .env.example .env
# Edit .env — minimum required: GROQ_API_KEY, SECRET_KEY, AES_KEY

# 2. Launch all 9 services
docker compose up --build -d

# 3. Verify
docker compose ps
curl http://localhost:8002/health
```

**Services started:**

| Container | Port | Role |
|---|---|---|
| `analyst-api` | 8002 | API Gateway |
| `analyst-governance` | — | Governance worker |
| `analyst-worker-sql` | — | SQL analysis |
| `analyst-worker-csv` | — | CSV analysis |
| `analyst-worker-json` | — | JSON analysis |
| `analyst-worker-pdf` | — | PDF RAG |
| `analyst-exporter` | — | Export service |
| `analyst-postgres` | 5433 | Metadata database |
| `analyst-redis` | 6379 | Broker + cache |
| `analyst-qdrant` | 6333 | Vector database |

### Kubernetes (Production)

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml
```

The `hpa.yaml` configures Horizontal Pod Autoscaler — the analysis workers scale automatically based on Celery queue depth.

---

## ⚡ Getting Started

### Prerequisites

- Docker + Docker Compose
- A [Groq API key](https://console.groq.com) (free tier)
- 4GB RAM minimum (8GB recommended for all workers)

### Quick Start

```bash
git clone https://github.com/OmarAbdelhamidAly/NTI-grad-project.git
cd NTI-grad-project
cp .env.example .env
```

Edit `.env`:
```bash
GROQ_API_KEY=gsk_...
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
AES_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
```

```bash
docker compose up --build -d
```

Open **http://localhost:8002** → Register → Upload a CSV → Ask a question.

### Run Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## ⚙️ Configuration

### Required Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for LLM calls (llama-3.1-8b-instant default) |
| `SECRET_KEY` | 64-char random hex for JWT signing — **never use default in production** |
| `AES_KEY` | Base64-encoded 32-byte key for SQL credential encryption |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

### Optional Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | `groq/llama-3.1-8b-instant` | Override LLM model per service |
| `ENV` | `development` | Set to `production` to enforce secret validation and hide API docs |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum CSV/file upload size |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |

---

## 🔧 Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **API Framework** | FastAPI + Uvicorn | 0.115.6 / 0.34.0 |
| **AI Orchestration** | LangGraph + LangChain | Latest |
| **LLM Provider** | Groq (Llama-3.1-8B / 3.3-70B) | ≥ latest |
| **Task Queue** | Celery + Redis | 5.4.0 / 5.2.1 |
| **Primary Database** | PostgreSQL + SQLAlchemy async | 16 / 2.0.36 |
| **Vector Database** | Qdrant (multi-vector ColPali) | Latest |
| **Authentication** | JWT (python-jose) + bcrypt | 3.3.0 / 4.2.1 |
| **Data Processing** | Pandas + NumPy | 2.2.3 / 1.26.4 |
| **Visualization** | Plotly.js (frontend) | CDN |
| **Frontend** | Vanilla JS ES9+ + CSS Glassmorphism | — |
| **Migrations** | Alembic | 1.14.1 |
| **Containerisation** | Docker Compose + Kubernetes | — |
| **Logging** | structlog | Latest |
| **Rate Limiting** | slowapi | Latest |
| **Testing** | pytest + httpx | Latest |

---

<div align="center">

**NTI Final Capstone Project — National Telecommunication Institute**

*420-hour intensive program in multi-agent systems, RAG pipelines, and LLM orchestration*

</div>
