<div align="center">

# 🤖 Insightify

**Autonomous Enterprise Data Analyst — Multi-Tenant SaaS Platform**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Cyclic%20StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Broker%20%2B%20HITL%20Checkpoint-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-12%20Containers-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.0--Flash%20Vision-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20RAG-4F46E5)](https://qdrant.tech)
[![CleanArch](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-blueviolet)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

<br/>

> *Connect your CSV, SQL database, JSON, or PDF. Ask a question in plain English. Get back a fully reasoned, chart-backed, cited insight — automatically.*

<br/>

**[🚀 Quick Start](#-getting-started) · [🏗️ Architecture](#-system-architecture) · [🔒 Security](#-security-architecture) · [📡 API Docs](NTI_API_DOCUMENTATION.md) · [🎬 Watch the Demo](#-demo)**

</div>

---

## 🎯 What It Does

**Insightify** is a production-grade, multi-tenant SaaS platform that transforms raw enterprise data into executive-quality insights through a fully autonomous multi-agent AI pipeline.

A user connects a data source, types a natural-language question, and the system handles everything else — schema discovery, query generation, self-healing on failure, visualization, insight synthesis, and export — with **zero manual intervention**.

### Supported Data Sources

| Source | Connection Method | Notes |
|---|---|---|
| **CSV / XLSX / SQLite** | File upload | Auto-profiled on upload |
| **PostgreSQL / MySQL** | Encrypted connection string | AES-256 credentials at rest |
| **JSON** | File upload | Structured event or log data |
| **PDF** | File upload | Native Multimodal Analysis via Gemini 2.0 Flash |

### What Makes It Different

| Feature | Description |
|---|---|
| 🔁 **Zero-Row Reflection** | If a SQL query returns 0 results, the agent detects the failure, analyzes case mismatches against `low_cardinality_values`, and auto-rewrites the query (up to 3 retries, no re-run from scratch) |
| 👁️ **Human-in-the-Loop (HITL)** | SQL queries against live databases pause at `interrupt_after=["human_approval"]`. Full LangGraph state serialized to Redis via `AsyncRedisSaver` — survives worker restarts, pod evictions, cluster reboots |
| 🧬 **Hybrid Fusion** | SQL results enriched with PDF context via **Gemini 2.0 Flash Multimodal** — pages rendered as images, semantically retrieved from Qdrant, synthesized into a unified insight |
| 🛡️ **3-Layer SQL Guardrails** | Layer 1: SELECT-only allowlist · Layer 2: DML/DDL regex blocklist · Layer 3: LLM semantic policy enforcement (tenant-scoped, natural-language rules) |
| 🏢 **Multi-Tenant Isolation** | Single DB, `tenant_id` scoped on every SQLAlchemy query. Enforced at the `get_current_user` dependency level — cannot be bypassed |
| ⚡ **Auto-Analysis on Upload** | 5 pre-generated analyses computed in background on upload — users see instant insights on first open, zero wait |
| 🧠 **Insight Memory** | Successful SQL queries saved as golden examples. Semantically retrieved as few-shot examples in future `analysis_generator` calls — improving accuracy over time |
| 🏗️ **Clean Architecture** | Every microservice follows Hexagonal Architecture: `domain → use_cases → modules → infrastructure`. Swapping LLM providers or databases requires changes only in the outermost ring |
| 📊 **Reasoning Transparency** | Every LangGraph node output captured in `thinking_steps` JSON and surfaced in the UI — full agent cognition audit trail per job |
| 🔄 **Multi-Provider LLM Resilience** | `OpenRouter (Gemini 2.0 Flash) → Groq (Llama-3.3-70B) → Gemini Direct` fallback chain. LLM provider outages are transparent to all agents |

---

## 🏗️ System Architecture

The platform is built as a **4-layer microservices stack** orchestrated by Docker Compose (Kubernetes for production):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           END USER / ADMIN                              │
│              Glassmorphism SPA (Vanilla JS + Plotly.js)                 │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTPS :8002
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 1 — API GATEWAY  (services/api · FastAPI · :8002)                │
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
      ┌──────────────────┬──────────────────┬──────────────────┐
      ▼                  ▼                  ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  LAYER 3      │ │  LAYER 3      │ │  LAYER 3      │ │  LAYER 3      │
│  worker-sql   │ │  worker-csv   │ │  worker-json  │ │  worker-pdf   │
│               │ │               │ │               │ │               │
│ 12-node       │ │ 11-node       │ │ 10-node       │ │ 10-node       │
│ Cyclic        │ │ Cyclic        │ │ Cyclic        │ │ Orchestrator  │
│ StateGraph    │ │ StateGraph    │ │ StateGraph    │ │ StateGraph    │
│               │ │               │ │               │ │               │
│ discovery →   │ │ discovery →   │ │ discovery →   │ │ refine →      │
│ generator →   │ │ [clean?] →    │ │ guardrail →   │ │ router →      │
│ [HITL] →      │ │ guardrail →   │ │ analysis →    │ │ retrieval →   │
│ execution →   │ │ analysis →    │ │ [reflect?] →  │ │ [vision/text/ │
│ [reflect?] →  │ │ [reflect?] →  │ │ visualization │ │  ocr] synth → │
│ hybrid_fusion→│ │ visualization→│ │ insight →     │ │ verifier →    │
│ visualization │ │ insight →     │ │ verifier →    │ │ analyst →     │
│ insight →     │ │ verifier →    │ │ recomm. →     │ │ assembler     │
│ verifier →    │ │ recomm. →     │ │ save_cache    │ └───────────────┘
│ recomm. →     │ │ assembler →   │ └───────────────┘
│ save_cache →  │ │ save_cache    │
│ assembler     │ └───────────────┘
└───────────────┘
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
                    + LangGraph HITL checkpoints (AsyncRedisSaver)
Qdrant :6333      — Vector DB for PDF knowledge base (multi-vector RAG)
```

> **Full C4 diagrams** (Context → Container → Component) available in [`NTI_C4_DIAGRAMS.md`](NTI_C4_DIAGRAMS.md).

---

## 📂 Repository Structure

```
insightify/
│
├── 📁 services/
│   ├── api/                      # Layer 1: Public API Gateway
│   │   └── app/
│   │       ├── main.py           # FastAPI app factory + self-healing DB migration
│   │       ├── routers/          # auth · users · data_sources · analysis
│   │       │                     # knowledge · policies · metrics · reports
│   │       ├── models/           # SQLAlchemy ORM: tenant · user · data_source
│   │       │                     # analysis_job · analysis_result · knowledge · policy
│   │       ├── schemas/          # Pydantic request/response schemas
│   │       ├── use_cases/        # Business logic: run_pipeline · auto_analysis · export
│   │       ├── infrastructure/
│   │       │   ├── config.py     # Pydantic Settings — all config from env vars
│   │       │   ├── security.py   # JWT access/refresh tokens + bcrypt password hashing
│   │       │   ├── sql_guard.py  # 3-layer SQL injection prevention
│   │       │   ├── middleware.py # CORS · rate limiting · security headers · logging
│   │       │   ├── token_blacklist.py # Redis-backed JWT revocation (JTI)
│   │       │   └── adapters/
│   │       │       ├── encryption.py  # AES-256-GCM for SQL credentials at rest
│   │       │       ├── qdrant.py      # Vector DB adapter (multi-vector ColPali)
│   │       │       └── storage.py     # Tenant-scoped file storage
│   │       ├── modules/shared/agents/ # Shared: intake · guardrail · output_assembler
│   │       └── static/           # Glassmorphism SPA (HTML + CSS + JS)
│   │
│   ├── governance/               # Layer 2: Policy + Guardrail worker
│   │   └── app/modules/governance/
│   │       ├── workflow.py       # LangGraph: intake → [clarify?] → guardrail
│   │       └── agents/           # intake_agent · guardrail_agent
│   │
│   ├── worker-sql/               # Layer 3: SQL analysis pipeline (11-node)
│   │   └── app/modules/sql/
│   │       ├── workflow.py       # LangGraph SQL graph
│   │       ├── agents/           # data_discovery · analysis_generator · execution
│   │       │                     # hybrid_fusion · visualization · insight
│   │       │                     # verifier · recommendation · memory_persistence
│   │       ├── tools/            # run_sql_query · sql_schema_discovery
│   │       └── utils/            # golden_sql · insight_memory · schema_mapper
│   │                             # schema_selector · sql_validator
│   │
│   ├── worker-csv/               # Layer 3: CSV/flat-file analysis pipeline (7-node)
│   │   └── app/modules/csv/
│   │       ├── workflow.py       # LangGraph CSV graph
│   │       ├── agents/           # data_discovery · data_cleaning · analysis
│   │       │                     # visualization · insight · recommendation
│   │       └── tools/            # clean_dataframe · compute_correlation
│   │                             # compute_ranking · compute_trend · profile_dataframe
│   │
│   ├── worker-json/              # Layer 3: JSON analysis pipeline
│   ├── worker-pdf/               # Layer 3: PDF Multimodal analysis (Gemini 2.0 Flash)
│   └── exporter/                 # Layer 4: Async PDF/XLSX/JSON export service
│
├── 📁 frontend/                  # React + TypeScript SPA (Vite)
│   └── src/                      # Component-based UI, Plotly.js charts
│
├── 📁 grafana/                   # Grafana dashboards + provisioning
│   └── provisioning/             # Datasources + pre-built dashboards
│
├── 📁 prometheus/                # Prometheus scrape config
│   └── prometheus.yml
│
├── 📁 k8s/                       # Kubernetes manifests (production)
│   ├── namespace.yaml
│   ├── api-deployment.yaml
│   ├── worker-deployment.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-deployment.yaml
│   ├── hpa.yaml                  # Horizontal Pod Autoscaler (queue-depth based)
│   ├── ingress.yaml
│   ├── pvc.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
│
├── 📁 tests/                     # Test suite (pytest + httpx)
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_data_sources.py
│   ├── test_analysis.py          # CSV + SQL pipeline integration tests
│   ├── test_health.py
│   └── test_architecture.py
│
├── 📁 alembic/                   # Database migrations
│   └── versions/                 # 001_initial · add_auto_analysis_fields
│
├── docker-compose.yml            # 10-service local stack (+ Prometheus + Grafana)
├── .env.example                  # All required environment variables documented
├── NTI_API_DOCUMENTATION.md      # Full REST API reference
├── NTI_ARCHITECTURE.md           # Architecture deep-dive
└── NTI_C4_DIAGRAMS.md            # C4 diagrams (Context → Container → Component)
```

---

## 🔧 Services Deep-Dive

### Layer 1 — API Gateway (`services/api`)

The single public entry point. Never executes analysis directly — validates, persists, and dispatches.

| Module | Role |
|---|---|
| `routers/auth.py` | Register, login, refresh, logout — JWT rotation + Redis JTI revocation |
| `routers/data_sources.py` | Upload CSV/XLSX/SQLite, connect SQL via AES-256 encrypted credentials, auto-profile schema |
| `routers/analysis.py` | Submit queries, poll job status, fetch results, approve HITL SQL jobs |
| `routers/knowledge.py` | Upload PDFs → Qdrant multi-vector ColPali indexing for hybrid SQL+PDF fusion |
| `routers/policies.py` | Admin-managed guardrail rules (e.g. "never expose PII columns") |
| `routers/metrics.py` | Job analytics, latency tracking, tenant usage stats |
| `routers/reports.py` | Export results as PDF/XLSX/JSON (dispatched to exporter worker) |
| `infrastructure/security.py` | JWT access (30min) + refresh (7 days) tokens, bcrypt passwords |
| `infrastructure/sql_guard.py` | 3-layer read-only enforcement: SELECT-only + regex + EXPLAIN cost |
| `infrastructure/middleware.py` | CORS, rate limiting, security headers (CSP, X-Frame-Options, etc.) |
| `infrastructure/adapters/encryption.py` | AES-256-GCM encryption for SQL connection strings stored in DB |

**Multi-tenant isolation:** every database query is scoped by `tenant_id` at the SQLAlchemy layer. A user from Tenant A cannot see, modify, or detect Tenant B's data.

**Self-healing startup:** the `lifespan` context manager runs idempotent `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every deploy — zero-downtime schema evolution.

---

### Layer 2 — Governance (`services/governance`)

Every analysis job passes through here first. No job reaches an execution pillar without governance approval.

```
START → [intake] → check_intake → [guardrail] → END
                        │
                        └── clarification_needed → END (asks user to rephrase)
```

- **Intake Agent:** classifies intent (`trend | comparison | ranking | correlation | anomaly`), extracts entities, detects ambiguous questions, assigns complexity index (1–5)
- **Guardrail Agent:** enforces admin-defined natural-language policies, checks for PII exposure, validates semantic safety

---

### Layer 3 — Execution Pillars

Four specialized Celery workers, each independently scalable:

| Worker | Queue | Pipeline Nodes | Graph Type | Key Capabilities |
|---|---|---|---|---|
| `worker-sql` | `pillar.sql / pillar.sqlite / pillar.postgresql` | **12** | Cyclic StateGraph | HITL approval, zero-row reflection, hybrid fusion, semantic cache, insight memory |
| `worker-csv` | `pillar.csv` | **11** | Cyclic StateGraph | Conditional data cleaning, guardrail, self-healing reflection, verifier |
| `worker-json` | `pillar.json` | **10** | Directed Cyclic StateGraph | MongoDB + Qdrant 768d RAG, semantic decomposition |
| `worker-pdf` | `pillar.pdf` | **10** | Orchestrator StateGraph | Gemini 2.0 Flash Vision, triple synthesis engines, anti-hallucination loop |

---

### Layer 4 — Exporter (`services/exporter`)

Async export worker. Generates PDF/XLSX/JSON reports from completed results. Writes to tenant-scoped shared volume, serves via signed download URLs.

---

### Observability — Prometheus + Grafana

The stack ships with a pre-configured observability layer:

- **Prometheus** scrapes API metrics (job counts, latencies, error rates, queue depths)
- **Grafana** dashboards provisioned automatically — no manual setup
- **Celery Flower** available for real-time task monitoring

Access Grafana at `http://localhost:3000` (admin/admin) after `docker compose up`.

---

## 🔄 LangGraph Pipelines

### SQL Pipeline (11 nodes)

```
START
  │
  ▼
[data_discovery]         ← Schema mapper: tables, columns, PKs, FKs, sample values,
  │                         low-cardinality enums, Mermaid ERD, schema compression
  ▼
[analysis_generator]     ← ReAct agent + golden SQL examples from insight_memory
  │                         Generates ANSI SELECT + execution plan
  ▼
route_after_generator
  ├── auto_analysis → [execution]              (bypasses HITL)
  └── user job       → [human_approval]        ← HITL INTERRUPT (Redis checkpointer)
                            │ admin approves in UI
                            ▼
                       [execution]             ← Runs approved SQL, fetches ≤1,000 rows
                            │
                       route_after_execution
                        ├── zero_rows → [backtrack] → [analysis_generator]  (max 3 retries)
                        └── success  → [hybrid_fusion]  ← Qdrant PDF context enrichment
                                            ▼
                                     [visualization]    ← Plotly chart JSON
                                            ▼
                                      [insight]         ← 3–5 sentence executive summary
                                            ▼
                                      [verifier]        ← Quality gate: insight vs data
                                            ▼
                                   [recommendation]     ← 3 actionable next steps
                                            ▼
                                  [memory_persistence]  ← Save to golden SQL examples
                                            ▼
                                  [output_assembler]    ← Final JSON output
                                            ▼
                                           END
```

**Self-healing mechanisms:**
- **Zero-Row Reflection:** `row_count=0` triggers literal extraction → comparison against `low_cardinality_values` → case-mismatch correction hint injected into retry
- **Backtrack Node:** on any error, adds strategic hint and re-routes to `analysis_generator` (max 3 retries)
- **Verifier Agent:** quality gate between insight and recommendation — rejects insights not supported by the actual data

---

### CSV Pipeline (7 nodes)

```
START → [data_discovery] → needs_cleaning?
            ├── YES (quality_score < 0.9) → [data_cleaning] → [analysis]
            └── NO                        →                   [analysis]
                                                                  ▼
                                                          [visualization]
                                                                  ▼
                                                            [insight]
                                                                  ▼
                                                         [recommendation]
                                                                  ▼
                                                       [output_assembler] → END
```

Data quality scoring: null ratio + type consistency + outlier density → automatic cleaning if score < 0.9.

---

### Governance Pipeline (2 nodes)

```
START → [intake] → check_intake → [guardrail] → END
                        └── clarification_needed → END
```

Runs before every analysis job. The only bypass is the `auto_analysis` system user (background jobs on upload).

---

## 🔒 Security Architecture

### Authentication — JWT with Refresh Rotation

```
Login → access_token (30min) + refresh_token (7 days)
     → Expired access token? POST /auth/refresh
     → Old refresh token REVOKED, new pair issued
     → Logout? JTI added to Redis blacklist (dead before expiry)
```

### SQL Injection Prevention — 3 Layers

```
Layer 1 — SELECT-only allowlist
    Query must start with SELECT or WITH (CTEs allowed)

Layer 2 — Regex blocklist
    Pattern: \b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|...)\b
    Applied to ALL SQL before any database connection

Layer 3 — LLM Semantic Guardrail
    Policy-aware semantic check (catches "comp" when policy says "never expose salary")
    Admin configures in plain English via /policies endpoint
```

### AES-256-GCM Credential Encryption

SQL connection strings encrypted before storage. Key lives exclusively in `AES_KEY` env var — if the var is lost, credentials are permanently unrecoverable by design.

### Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /auth/register` | 3 req/min |
| `POST /auth/login` | 5 req/min |
| All other endpoints | 200 req/min |

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
├── plan VARCHAR(50)        "internal" | "pro" | "enterprise"
└── created_at TIMESTAMPTZ

users
├── id UUID PK
├── tenant_id UUID FK → tenants
├── email TEXT UNIQUE
├── password_hash TEXT
├── role VARCHAR(10)        "admin" | "viewer"
├── created_at TIMESTAMPTZ
└── last_login TIMESTAMPTZ

data_sources
├── id UUID PK
├── tenant_id UUID FK → tenants
├── type VARCHAR(10)               "csv" | "sql" | "document"
├── name TEXT
├── file_path TEXT                 /tmp/tenants/{tenant_id}/file.csv
├── config_encrypted TEXT          AES-256-GCM encrypted connection JSON
├── schema_json JSON               columns, types, row count, sample values
├── auto_analysis_status VARCHAR   "pending"|"running"|"done"|"failed"
├── auto_analysis_json JSON        5 pre-generated analyses (computed on upload)
├── domain_type VARCHAR(30)        "sales"|"hr"|"finance"|"inventory"|"customer"
└── created_at TIMESTAMPTZ

analysis_jobs
├── id UUID PK
├── tenant_id UUID FK → tenants
├── user_id UUID FK → users
├── source_id UUID FK → data_sources
├── question TEXT
├── intent VARCHAR(50)             "trend"|"comparison"|"ranking"|"correlation"|"anomaly"
├── status VARCHAR(20)             "pending"|"running"|"done"|"error"|"awaiting_approval"
├── generated_sql TEXT             SQL shown to admin for HITL review
├── thinking_steps JSON            LangGraph node outputs (powers UI "Reasoning" panel)
├── complexity_index INTEGER        1–5 scale (from intake agent)
├── total_pills INTEGER             number of analysis sub-questions
├── retry_count INTEGER
├── kb_id UUID FK → knowledge_bases  (optional — enables PDF hybrid fusion)
├── started_at TIMESTAMPTZ
├── completed_at TIMESTAMPTZ
└── error_message TEXT

analysis_results
├── id UUID PK
├── job_id UUID FK → analysis_jobs (1:1)
├── charts JSON                    array of Plotly chart specs
├── insight_report TEXT            executive summary
├── recommendations JSON           array of action items
├── data_snapshot JSON             first 100 rows of query result
└── embedding JSON                 result embedding for similarity search

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
├── rule TEXT                      natural language guardrail rule
├── is_active BOOLEAN
└── created_at TIMESTAMPTZ
```

---

## 🚀 Deployment

### Docker Compose — Local / Staging

```bash
# 1. Clone and configure
git clone https://github.com/OmarAbdelhamidAly/insightify.git
cd insightify
cp .env.example .env
# Edit .env — minimum required: GROQ_API_KEY, SECRET_KEY, AES_KEY

# 2. Launch all services
docker compose up --build -d

# 3. Verify
docker compose ps
curl http://localhost:8002/health
```

**Services started:**

| Container | Port | Role |
|---|---|---|
| `analyst-api` | 8002 | API Gateway + SPA |
| `analyst-governance` | — | Governance worker |
| `analyst-worker-sql` | — | SQL analysis (11-node) |
| `analyst-worker-csv` | — | CSV analysis (7-node) |
| `analyst-worker-json` | — | JSON analysis |
| `analyst-worker-pdf` | — | PDF RAG (ColPali) |
| `analyst-exporter` | — | Export service |
| `analyst-postgres` | 5433 | Metadata database |
| `analyst-redis` | 6379 | Broker + cache + HITL checkpoints |
| `analyst-qdrant` | 6333 | Vector database |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Monitoring dashboards |

### Kubernetes — Production

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/hpa.yaml      # Auto-scales workers by queue depth
kubectl apply -f k8s/ingress.yaml
```

---

## ⚡ Getting Started

### Prerequisites

- Docker + Docker Compose v2
- [Groq API key](https://console.groq.com) (free tier)
- 4 GB RAM minimum (8 GB recommended)

### Quick Start

```bash
git clone https://github.com/OmarAbdelhamidAly/insightify.git
cd insightify
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
| `GROQ_API_KEY` | Groq API key — `llama-3.1-8b-instant` default, `llama-3.3-70b-versatile` for production |
| `SECRET_KEY` | 64-char random hex for JWT signing — **never use default in production** |
| `AES_KEY` | Base64-encoded 32-byte key for SQL credential encryption |
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |

### Optional Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | `groq/llama-3.1-8b-instant` | Override LLM model per service |
| `ENV` | `development` | Set to `production` to enforce secret validation + hide API docs |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum CSV/file upload size |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |

---

## 🔧 Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **API Framework** | FastAPI + Uvicorn | 0.115.6 / 0.34.0 |
| **Architecture Pattern** | Clean (Hexagonal) Architecture | — |
| **AI Orchestration** | LangGraph `StateGraph` (Cyclic) | Latest |
| **LLM Primary** | OpenRouter → `google/gemini-2.0-flash-001` | Latest |
| **LLM Fallback 1** | Groq → Llama-3.3-70B / 3.1-8B | Latest |
| **LLM Fallback 2** | Gemini Direct API → `gemini-2.0-flash-exp` | Latest |
| **PDF Vision** | Gemini 2.0 Flash Vision (Multimodal) | Latest |
| **Task Queue** | Celery + Redis (`AsyncRedisSaver` for HITL) | 5.4.0 / 5.2.1 |
| **Primary Database** | PostgreSQL 16 + SQLAlchemy async | 2.0.36 |
| **Vector Database** | Qdrant (768d — JSON RAG + PDF embeddings) | Latest |
| **Document Store** | MongoDB (JSON pipeline) | Latest |
| **Authentication** | JWT (python-jose) + bcrypt + Redis JTI blacklist | 3.3.0 / 4.2.1 |
| **Encryption** | AES-256-GCM (SQL credential storage) | — |
| **Data Processing** | Pandas + NumPy | 2.2.3 / 1.26.4 |
| **Visualization** | ECharts + Plotly.js | CDN |
| **Frontend** | React + TypeScript + Vite (+ Vanilla JS SPA) | Latest |
| **Containerisation** | Docker Compose (22 services) + Kubernetes HPA | — |
| **Observability** | Prometheus + Grafana (auto-provisioned) | Latest |
| **Logging** | structlog (structured JSON) | Latest |
| **Rate Limiting** | slowapi | Latest |
| **Testing** | pytest + httpx | Latest |

---

## 🎬 Demo

> **Business Demo Video** available — produced with Pippit AI.
> See [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the full script and voiceover used.

---

<div align="center">

**NTI Final Capstone Project — National Telecommunication Institute, Egypt**

*420-hour intensive program in multi-agent systems, RAG pipelines, and LLM orchestration*

Built by a team of AI engineers committed to production-grade, enterprise-ready systems.

> An open, composable alternative to **Amazon Q Business** — designed for any organization sitting on fragmented multi-modal data.

⭐ If this project helped you, please star the repository.

**Full Architecture Documentation:**
- 🏛️ [Architecture Deep-Dive](NTI_ARCHITECTURE.md) — Clean Architecture, all 4 LangGraph pipelines, security, deployment
- 📐 [C4 Diagrams](NTI_C4_DIAGRAMS.md) — Context → Container → Component → Code level diagrams
- 📡 [API Documentation](NTI_API_DOCUMENTATION.md) — All endpoints, request/response schemas, RBAC table

</div>
