<div align="center">

# 🤖 OpenQ

**Autonomous Multi-Pillar Enterprise Data Intelligence — Multi-Tenant SaaS Platform**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Cyclic%20StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-Broker%20%2B%20HITL%20Checkpoint-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-21%20Containers-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.0--Flash%20Vision-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge%20Graph-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20RAG-4F46E5)](https://qdrant.tech)
[![CleanArch](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-blueviolet)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

<br/>

> *Connect CSV, SQL, JSON, PDF, source code, audio, image, or video. Ask a question in plain English. Get back a fully reasoned, chart-backed, cross-domain insight — automatically.*

<br/>

**[🚀 Quick Start](#-getting-started) · [🏗️ Architecture](#-system-architecture) · [🔒 Security](#-security-architecture) · [📡 API Docs](NTI_API_DOCUMENTATION.md) · [🎬 Demo](#-demo)**

</div>

---

## 🎯 What It Does

**OpenQ** is a production-grade, multi-tenant SaaS platform that transforms raw enterprise data into executive-quality insights through a fully autonomous, multi-pillar AI pipeline.

A user connects a data source, types a natural-language question, and the system handles everything — schema discovery, query generation, self-healing on failure, visualization, insight synthesis, and export — with **zero manual intervention**.

### Supported Data Sources

| Source | Pillar | Connection Method | Notes |
|---|---|---|---|
| **Universal Text / CSV / PDF** | `worker-pdf` | File upload | Multimodal Vision decoding + GraphRAG Semantic Weaver. |
| **PostgreSQL / MySQL** | `worker-sql` | Encrypted connection string | Golden SQL memory + HITL + GDS-Aware Retrieval. |
| **JSON** | `worker-json` | File upload | Semantic flattening + NoSQL/Vector Hybrid Search. |
| **Source Code** | `worker-code` | Neo4j GDS | AST-parsed GDS Weaver (Louvain Modules & PageRank). |
| **Audio** | `worker-audio` | Gemini Flash | Native Multimodal Transcription + Fast Retrieval (Skip-Indexing). |
| **Multi-pillar** | `worker-nexus` | Federated Graph | Strategic Orchestrator of the GraphRAG Pillar Federation. |


---

### What Makes It Different

| Feature | Description |
|---|---|
| 🔀 **Vector Semantic Routing** | SQL/DB schema discovery bypassing regex: `FastEmbed` and Cosine Similarity route queries to exact schemas via `worker-sql`. |
| 🧬 **Multi-Query RAG-Fusion** | The `worker-nexus` orchestrator breaks down complex questions into sub-queries and uses a **Cross-Encoder Re-Ranker** to filter noise. |
| 🛡️ **Native RAG Quality Evaluator** | Completely free, local, self-evaluating metrics. Zero-cost dual small language models (`ms-marco` + NLI) measure *Avg Relevance*, *Utilization*, and *Attribution* natively exposed to **Prometheus/Grafana** dashboards. |
| 🚀 **WebSockets & gRPC** | Real-time streaming of LLM `thinking_steps` via Redis Pub/Sub WebSockets (Zero REST Polling). |
| 🔁 **Zero-Row Reflection** | SQL queries returning 0 rows trigger automatic case-mismatch detection against `low_cardinality_values` and self-correcting retry (max 3 iterations, no cold restart) |
| 👁️ **Human-in-the-Loop (HITL)** | SQL queries against live databases pause at `interrupt_after=["human_approval"]`. Full LangGraph state serialized to Redis via `AsyncRedisSaver` — survives worker restarts, pod evictions, cluster reboots |
| 🧬 **Hybrid Retrieval Matrix** | SQL results enriched with PDF/Audio context via parallel Vector (Qdrant) and Graph (Neo4j) search. Uses Text-to-Cypher to traverse relationships that cross-pillar reasoning flows require. |
| 🧬 **Strategic GraphRAG** | Transitioned all unstructured pillars (Audio, Code, PDF) to a native **Neo4j GDS** backend. Uses Louvain communities and PageRank centrality to discover semantic hierarchies and architectural "Logical Hearts" autonomously. |
| 🧬 **Semantic Weaver** | Post-indexing background process that "weaves" the knowledge graph by identifying k-NN similarities, clustering thematic communities, and generating hierarchical summaries for global document reasoning. |

| 🛡️ **3-Layer SQL Guardrails** | Layer 1: SELECT-only allowlist · Layer 2: DML/DDL regex blocklist · Layer 3: LLM semantic policy enforcement (tenant-scoped, natural-language rules) |
| 🏢 **Multi-Tenant Isolation** | Single DB, `tenant_id` scoped on every SQLAlchemy query. Enforced at the `get_current_user` dependency level — cannot be bypassed |
| ⚡ **Auto-Analysis on Upload** | 5 pre-generated analyses computed in background on upload — users see instant insights on first open, zero wait |
| 🧠 **Insight Memory** | Successful SQL queries saved as golden examples. Semantically retrieved as few-shot examples in future `analysis_generator` calls — improving accuracy over time |
| 🏗️ **Clean Architecture** | Every microservice follows Hexagonal Architecture: `domain → use_cases → modules → infrastructure`. Swapping LLM providers or databases requires changes only in the outermost ring |
| 📊 **Reasoning Transparency** | Every LangGraph node output captured in `thinking_steps` JSON and surfaced in the UI — full agent cognition audit trail per job |
| 🔄 **Multi-Provider LLM Resilience** | `OpenRouter (Gemini 2.0 Flash-001) → Groq (Llama-3.3-70B) → Gemini Direct` fallback chain. LLM provider outages are transparent to all agents |
| 🎙️ **Voice Queries** | Natural-language questions submitted as audio — transcribed server-side and routed through the standard analysis pipeline |
| 🎙️ **Voice Queries** | Natural-language questions submitted as audio — transcribed server-side and routed through the standard analysis pipeline |

---

## 🏗️ System Architecture

The platform is a **5-layer microservices stack** with **21 containers**, orchestrated by Docker Compose (Kubernetes-ready for production):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           END USER / ADMIN                              │
│  Glassmorphism SPA (Vanilla JS + ECharts/Plotly)                        │
│  React + TypeScript SPA (Vite, frontend/)                               │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTPS :8002
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 1 — API GATEWAY  (services/api · FastAPI · :8002)                │
│                                                                          │
│  JWT auth + refresh rotation · Rate limiting · AES-256-GCM encrypt      │
│  Multi-tenant routing · WebSockets (Streaming UX) · Celery task dispatch │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Celery tasks via Redis
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 2 — GOVERNANCE  (services/governance · Celery worker)            │
│                                                                          │
│  Intake Agent — intent classification, entity extraction, complexity     │
│  Guardrail Agent — LLM policy enforcement, PII detection                │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Celery tasks by type
       ┌────────┬────────┬───────┼─────────┬────────┐
       ▼        ▼        ▼       ▼         ▼        ▼
┌──────────┐ ┌──────┐ ┌──────┐ ┌───────┐ ┌──────┐ ┌──────┐
│LAYER 3   │ │      │ │      │ │       │ │      │ │      │
│worker-sql│ │ api  │ │ json │ │ doc   │ │ code │ │nexus │
│          │ │      │ │      │ │(pdf/  │ │      │ │      │
│12-node   │ │      │ │10-nd │ │ csv)  │ │8-nd  │ │Multi-│
│Cyclic    │ │      │ │Cyclic│ │ Univ. │ │Cyclic│ │Pillar│
│StateGraph│ │      │ │      │ │ Graph │ │      │ │      │
└──────────┘ └──────┘ └──────┘ └───────┘ └──────┘ └──────┘
                                   │
                   ┌───────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  worker-nexus — Federated Multi-Pillar Orchestrator                     │
│  Neo4j cross-pillar forge → RAG-Fusion → Re-Ranking → 5-pillar synthesis│
└──────────────────────────────────────────────────────────────────────────┘
                                   │
│  LAYER 4 — EXPORTER  (services/exporter · Celery worker)               │
│  PDF / XLSX / JSON export · Async generation · Tenant-scoped storage   │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│  LAYER 5 — CORPORATE  (services/corporate · FastAPI + gRPC · :8009)    │
│  Org-Tree (20 levels) · Task Governance · Sub-ms Auth via Protobuf      │
└─────────────────────────────────────────────────────────────────────────┘

SHARED INFRASTRUCTURE
─────────────────────────────────────────────────────────────────────────
PostgreSQL :5433  — Metadata: tenants, users, jobs, results, policies
Redis :6379       — Celery broker + result backend + JWT JTI blacklist
                    + LangGraph HITL checkpoints (AsyncRedisSaver)
Qdrant :6333      — Vector DB: JSON RAG + PDF chunk embeddings
Neo4j             — Knowledge Graph: code AST, audio/image entities,
                    cross-pillar relationships
MongoDB           — Document store for JSON pillar aggregation pipelines
```

> **Full C4 diagrams** (Context → Container → Component → Code) in [`NTI_C4_DIAGRAMS.md`](NTI_C4_DIAGRAMS.md).

---

## 📂 Repository Structure

```
OpenQ/
│
├── 📁 services/
│   ├── api/                      # Layer 1: Public API Gateway
│   ├── corporate/                # Layer 5: Org-Tree & Task Governance
│   │   └── app/
│   │       ├── main.py           # FastAPI app factory + self-healing DB migration
│   │       ├── routers/          # auth · users · data_sources · analysis
│   │       │                     # knowledge · policies · metrics · reports
│   │       │                     # groups · voice
│   │       ├── models/           # SQLAlchemy ORM: tenant · user · data_source
│   │       │                     # analysis_job · analysis_result · knowledge · policy
│   │       ├── schemas/          # Pydantic request/response schemas
│   │       ├── use_cases/        # run_pipeline · auto_analysis · export
│   │       ├── infrastructure/
│   │       │   ├── config.py     # Pydantic Settings — all config from env vars
│   │       │   ├── security.py   # JWT access/refresh tokens + bcrypt
│   │       │   ├── sql_guard.py  # 3-layer SQL injection prevention
│   │       │   ├── middleware.py # CORS · rate limiting · security headers
│   │       │   ├── token_blacklist.py # Redis-backed JWT JTI revocation
│   │       │   └── adapters/
│   │       │       ├── encryption.py  # AES-256-GCM SQL credential encryption
│   │       │       ├── qdrant.py      # Vector DB adapter (multi-vector)
│   │       │       └── storage.py     # Tenant-scoped file storage
│   │       └── static/           # Glassmorphism SPA (HTML + CSS + JS)
│   │
│   ├── governance/               # Layer 2: Policy + Guardrail worker
│   │   └── app/modules/governance/
│   │       ├── workflow.py       # LangGraph: intake → [clarify?] → guardrail
│   │       └── agents/           # intake_agent · guardrail_agent
│   │
│   ├── worker-sql/               # Layer 3: SQL analysis pipeline (12 nodes)
│   │   └── app/modules/sql/
│   │       ├── workflow.py       # LangGraph SQL graph + HITL + Redis checkpointer
│   │       ├── agents/           # data_discovery · analysis_generator · reflection
│   │       │                     # human_approval · execution · hybrid_fusion
│   │       │                     # visualization · insight · verifier
│   │       │                     # recommendation · save_cache · evaluation
│   │       │                     # output_assembler
│   │       ├── tools/            # run_sql_query · sql_schema_discovery
│   │       └── utils/            # golden_sql · insight_memory · rag_evaluator
│   │
│   ├── worker-json/              # Layer 3: JSON pipeline (10 nodes, MongoDB + Qdrant)
│   ├── worker-pdf/               # Layer 3: Universal Document (Unstructured Text & Multimodal PDF)
│   ├── worker-audio/             # Layer 3: Audio Intelligence (9 nodes, Whisper/Gemini audio, Qdrant+Neo4j)
│   │   └── app/modules/audio/
│   │       ├── workflow.py       # LangGraph: profiler → transcription → diarization
│   │       │                     # → entity_extractor → summarizer → evaluator → memory
│   │       └── agents/           # preprocessor_agent · diarization_agent...
│   │
│   ├── worker-code/              # Layer 3: Codebase AST pipeline (8 nodes, Neo4j)
│   │   └── app/modules/code/
│   │       ├── workflow.py       # LangGraph: discovery → generator → execution
│   │       │                     # → insight → memory → evaluator → save_cache
│   │       └── agents/           # data_discovery · cypher_generator · evaluation
│   │
│   ├── worker-nexus/             # Layer 3: Federated multi-pillar orchestrator
│   │   └── app/modules/nexus/
│   │       ├── workflow.py       # LangGraph: router → explorer → orchestrator
│   │       │                     # → synthesizer → memory → save_cache
│   │       └── agents/           # nexus_router · graph_explorer
│   │                             # pillar_orchestrator · synthesis_engine
│   │                             # memory_manager · semantic_cache
│   │
│   └── exporter/                 # Layer 4: Async PDF/XLSX/JSON export service
│
├── 📁 frontend/                  # React + TypeScript SPA (Vite)
│   └── src/                      # Component-based UI, ECharts, DataProfiler
│
├── 📁 grafana/                   # Grafana dashboards + auto-provisioning
├── 📁 prometheus/                # Prometheus scrape config
├── 📁 k8s/                       # Kubernetes manifests (production-grade)
│   ├── namespace.yaml            # analyst-ai namespace
│   ├── api-deployment.yaml
│   ├── worker-deployment.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-deployment.yaml
│   ├── hpa.yaml                  # Horizontal Pod Autoscaler (queue-depth based)
│   ├── ingress.yaml              # TLS termination + path routing
│   ├── pvc.yaml · configmap.yaml · secrets.yaml
│
├── 📁 terraform/                 # Infrastructure-as-Code — AWS (EKS + Aurora + ElastiCache + ECR)
│   ├── main.tf                   # KMS · Route 53 · ALB · 6 Modules
│   ├── variables.tf              # Region, domain_name, cluster specs
│   ├── outputs.tf                # VPC ID, EKS endpoint, Aurora + Redis endpoints
│   └── modules/
│       ├── vpc/                  # VPC, public/private subnets, NAT gateway
│       ├── eks/                  # EKS cluster (t3.large nodes)
│       ├── database/             # Aurora Serverless v2 PostgreSQL (0.5–2.0 ACUs)
│       ├── cache/                # ElastiCache Redis (managed broker + HITL cache)
│       ├── ecr/                  # Elastic Container Registry (image storage)
│       └── iam-cicd/             # IAM role + policy for CI/CD pipeline
│
├── docker-compose.yml            # 22-service local stack
├── .env.example                  # All required environment variables documented
├── NTI_API_DOCUMENTATION.md      # Full REST API reference
├── NTI_ARCHITECTURE.md           # Architecture deep-dive
└── NTI_C4_DIAGRAMS.md            # C4 diagrams (Context → Container → Component → Code)
```

---

## 🔧 Services Deep-Dive

### Layer 1 — API Gateway ([services/api](services/api/README.md))

The single public entry point. Validates, persists, and dispatches — never executes analysis directly.

| Module | Role |
|---|---|
| `routers/auth.py` | Register, login, refresh, logout — JWT rotation + Redis JTI revocation |
| `routers/data_sources.py` | Upload CSV/XLSX/SQLite/JSON/PDF/audio/image/video, connect SQL via AES-256-GCM encrypted credentials, auto-profile schema |
| `routers/analysis.py` | Submit queries, poll job status, approve/reject HITL SQL jobs |
| `routers/knowledge.py` | Upload PDFs → Qdrant multi-vector indexing for hybrid SQL+PDF fusion |
| `routers/policies.py` | Admin-managed natural-language guardrail rules |
| `routers/metrics.py` | Job analytics, latency tracking, tenant usage stats |
| `routers/reports.py` | Export results as PDF/XLSX/JSON (dispatched to exporter worker) |
| `routers/groups.py` | Team group management for multi-user tenants |
| `routers/voice.py` | Voice-to-text query submission (audio → transcription → analysis pipeline) |
| `infrastructure/security.py` | JWT access (30 min) + refresh (7 days) tokens, bcrypt passwords |
| `infrastructure/sql_guard.py` | 3-layer read-only enforcement: SELECT-only + regex + LLM semantic |
| `infrastructure/middleware.py` | CORS, rate limiting (slowapi), security headers (CSP, X-Frame-Options, etc.) |
| `infrastructure/adapters/encryption.py` | AES-256-GCM encryption for SQL connection strings stored in DB |

**Multi-tenant isolation:** every database query is scoped by `tenant_id` at the SQLAlchemy layer. Tenant A cannot see, modify, or detect Tenant B's data.

**Self-healing startup:** the `lifespan` context manager acquires a PostgreSQL advisory lock, runs idempotent `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every deploy — zero-downtime schema evolution.

---

### Layer 2 — Governance ([services/governance](services/governance/README.md))

Every analysis job passes through here first. No job reaches an execution pillar without governance approval.

```
START → [intake_agent] → check_intake → [guardrail_agent] → route_to_pillar → END
                                │
                                └── clarification_needed → END (asks user to rephrase)
```

- **Intake Agent:** classifies intent (`trend | comparison | ranking | correlation | anomaly`), extracts entities, detects ambiguity, assigns complexity index (1–5)
- **Guardrail Agent:** enforces admin-defined natural-language policies, checks PII exposure, validates semantic safety

---

### Layer 3 — Execution Pillars (8 specialized workers)

Each is an independently scalable Docker container with its own `requirements.txt`:

| Worker | Queue | Pipeline | Key Capabilities |
|---|---|---|---|
| [worker-sql](services/worker-sql/README.md) | `pillar.sql / .sqlite / .postgresql` | **12-node Cyclic StateGraph** | HITL approval, zero-row reflection, hybrid fusion, semantic cache, insight memory |
| [worker-csv](services/worker-csv/README.md) | `pillar.csv` | **11-node Cyclic StateGraph** | Conditional data cleaning, guardrail, self-healing reflection, verifier |
| [worker-json](services/worker-json/README.md) | `pillar.json` | **10-node Directed Cyclic StateGraph** | MongoDB aggregation + Qdrant 768d RAG, semantic decomposition |
| [worker-pdf](services/worker-pdf/README.md) | `pillar.pdf` | **10-node Orchestrator StateGraph** | Gemini 2.0 Flash Vision, triple synthesis engines, anti-hallucination loop |
| [worker-code](services/worker-code/README.md) | `pillar.code` | **8-node Cyclic StateGraph** | Neo4j AST-mapped codebase, Cypher generation, episodic memory |
| [worker-audio](services/worker-audio/README.md) | `pillar.audio` | Direct task (Gemini 1.5 Flash) | Transcript, speaker diarization, entity extraction, Neo4j sync |
| [worker-image](services/worker-image/README.md) | `pillar.image` | Direct task (Gemini multimodal) | Object/scene recognition, entity extraction, Neo4j sync |
| [worker-video](services/worker-video/README.md) | `pillar.video` | Direct task (Gemini multimodal) | Scene analysis, entity extraction, Neo4j sync |
| [worker-nexus](services/worker-nexus/README.md) | `pillar.nexus` | **6-node Federated Orchestrator** | Cross-pillar Neo4j forge → context gather → 5-pillar strategic synthesis |

---

### Layer 4 — Exporter ([services/exporter](services/exporter/README.md))

Async export worker. Generates PDF/XLSX/JSON reports from completed results. Writes to tenant-scoped shared volume, serves via signed download URLs.

---

### Observability — Prometheus + Grafana

- **Prometheus** scrapes API metrics at `/metrics` (job counts, latencies, error rates, queue depths)
- **Grafana** dashboards provisioned automatically — no manual setup
- **Celery Flower** available for real-time task monitoring

Access Grafana at `http://localhost:3000` (admin/admin) after `docker compose up`.

---

## 🔄 LangGraph Pipelines

### SQL Pipeline — 12 Nodes (Cyclic StateGraph)

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
  ├── error + retry < 3  → [reflection]           ← Corrective hint injection
  ├── auto_analysis      → [execution]             ← Bypasses HITL
  └── user job           → [human_approval]        ← HITL INTERRUPT (Redis checkpoint)
                               │ admin approves in UI
                               ▼
                          [execution]              ← Runs approved SQL (≤1,000 rows)
                               │
                          route_after_execution
                           ├── zero_rows / error + retry < 3 → [reflection]
                           │      └── case-mismatch detected against low_cardinality_values
                           │          retry_count++ → back to [execution]
                           └── success → [hybrid_fusion]  ← Qdrant PDF context enrichment
                                             ▼
                                      [visualization]    ← ECharts/Plotly chart JSON
                                             ▼
                                        [insight]        ← 3–5 sentence executive summary
                                             ▼
                                        [verifier]       ← Quality gate: insight vs data
                                             ▼
                                     [recommendation]   ← 3 actionable next steps
                                             ▼
                                       [save_cache]     ← Semantic cache (Redis + Qdrant)
                                             ▼
                                   [output_assembler]   ← Final JSON → PostgreSQL write
                                             ▼
                                            END
```

---

### CSV Pipeline — 11 Nodes (Cyclic StateGraph)

```
START → [data_discovery] → needs_cleaning? (quality_score < 0.9)
            ├── YES → [data_cleaning] → [guardrail] → [analysis]
            └── NO                  →  [guardrail] → [analysis]
                                                         ▼
                                                check_analysis_result
                                                 ├── error + retry < 3 → [reflection] → [analysis]
                                                 └── success → [visualization] → [insight]
                                                                    → [verifier] → [recommendation]
                                                                    → [output_assembler] → [save_cache] → END
```

---

### JSON Pipeline — 10 Nodes (Directed Cyclic StateGraph)

Backed by **MongoDB** for document intelligence, **Qdrant** (768d vectors) for semantic RAG.

```
START → [data_discovery] → [guardrail] → [analysis] →
    ├── error + retry < 3 → [reflection] → [analysis]
    └── success → [visualization] → [insight] → [verifier]
               → [recommendation] → [output_assembler] → [save_cache] → END
```

---

### PDF Pipeline — 10 Nodes (Orchestrator-Worker StateGraph)

Three specialist synthesis engines routed by the master orchestrator:

```
START → [refine] → [router]
                     ├── "greeting" → [chat] → [output_assembler] → END
                     └── "analysis" → [retrieval]
                                          ├── reflection_needed → [refine]
                                          ├── mode=deep_vision  → [vision_synthesis]  (Gemini 2.0 Flash Vision)
                                          ├── mode=fast_text    → [text_synthesis]
                                          └── mode=hybrid       → [ocr_synthesis]
                                                    ↓
                                               [verifier] ← anti-hallucination loop
                                                    ├── verified=False + retry < 2 → re-route to synthesis engine
                                                    └── verified=True → [analyst] → [output_assembler] → END
```

---

### Code Pipeline — 8 Nodes (Cyclic StateGraph, Neo4j)

Codebase mapped as an Abstract Syntax Tree in Neo4j. Pure Cypher-based reasoning.

```
START → [discovery] → [generator] →
    ├── error + retry < 3  → [reflection] → [generator]
    ├── error + retry >= 3 → END
    └── success → [execution]
                     ├── error + retry < 3 → [reflection] → [generator]
                     └── success → [insight] → [memory] → [save_cache] → [assembler] → END
```

---

### Nexus Pipeline — 6 Nodes (Federated Orchestrator)

Triggers cross-domain intelligence across all pillars simultaneously. Backed by Neo4j knowledge graph.

```
START → [router] →
    ├── explore        → [explorer] → [orchestrator]
    ├── direct_query   →              [orchestrator]
    └── finalize       →                             → [synthesizer]
                                                            ▼
                                                        [memory] → [save_cache] → END
```

The `pillar_orchestrator` forges cross-pillar relationships in Neo4j (Code↔SQL, Entity↔Target, Chunk↔Mention), gathers multi-source context, and passes a structured 5-pillar context block to `synthesis_engine` for LLM-driven strategic report generation.

---

## 🔒 Security Architecture

### Authentication — JWT with Refresh Rotation

```
Login → access_token (30min) + refresh_token (7 days)
     → Expired access token? POST /auth/refresh
     → Old refresh token REVOKED (JTI added to Redis blacklist)
     → New pair issued
     → Logout? JTI blacklisted — token dead before natural expiry
```

### SQL Injection Prevention — 3 Layers in Sequence

```
Layer 1 — SELECT-only allowlist
    Query must start with SELECT or WITH (CTEs allowed)

Layer 2 — Regex blocklist
    \b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|EXEC|GRANT|REVOKE|MERGE|...)\b

Layer 3 — LLM Semantic Guardrail (executed in governance worker)
    Policy-aware semantic check — catches "comp" when policy says "never expose salary"
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
├── group_id UUID FK → team_groups  (optional)
├── created_at TIMESTAMPTZ
└── last_login TIMESTAMPTZ

data_sources
├── id UUID PK
├── tenant_id UUID FK → tenants
├── type VARCHAR(20)               "csv" | "sql" | "json" | "pdf" | "codebase"
│                                  "audio" | "image" | "video"
├── name TEXT
├── file_path TEXT
├── config_encrypted TEXT          AES-256-GCM encrypted connection JSON
├── schema_json JSON               columns, types, row count, sample values,
│                                  low_cardinality_values (used by zero-row reflection)
├── auto_analysis_status VARCHAR   "pending"|"running"|"done"|"failed"
├── auto_analysis_json JSON        5 pre-generated analyses (computed on upload)
├── domain_type VARCHAR(30)        "sales"|"hr"|"finance"|"inventory"|"customer"
├── indexing_status VARCHAR        "pending"|"done"|"failed" (Neo4j / Qdrant indexing)
└── created_at TIMESTAMPTZ

analysis_jobs
├── id UUID PK
├── tenant_id UUID FK
├── user_id UUID FK
├── source_id UUID FK → data_sources
├── question TEXT
├── intent VARCHAR(50)             "trend"|"comparison"|"ranking"|"correlation"|"anomaly"
├── status VARCHAR(20)             "pending"|"running"|"done"|"error"|"awaiting_approval"
├── generated_sql TEXT             SQL surfaced to admin for HITL review
├── thinking_steps JSON            LangGraph node outputs (powers UI Reasoning panel)
├── complexity_index INTEGER        1–5 scale (from intake agent)
├── retry_count INTEGER
├── kb_id UUID FK → knowledge_bases  (optional — enables PDF hybrid fusion)
├── started_at TIMESTAMPTZ
├── completed_at TIMESTAMPTZ
└── error_message TEXT

analysis_results
├── id UUID PK
├── job_id UUID FK → analysis_jobs (1:1)
├── charts JSON                    array of ECharts/Plotly chart specs
├── insight_report TEXT            executive summary
├── exec_summary TEXT              one-line summary
├── recommendations JSON           array of action items
├── follow_up_suggestions JSON     suggested next questions
├── data_snapshot JSON             first 100 rows of query result
└── embedding JSON                 result embedding for similarity search

knowledge_bases
├── id UUID PK
├── tenant_id UUID FK
├── name TEXT
├── description TEXT
└── created_at TIMESTAMPTZ

policies
├── id UUID PK
├── tenant_id UUID FK
├── name TEXT
├── rule TEXT                      natural language guardrail rule
├── is_active BOOLEAN
└── created_at TIMESTAMPTZ

team_groups
├── id UUID PK
├── tenant_id UUID FK
├── name TEXT
├── description TEXT
└── created_at TIMESTAMPTZ
```

---

## 🚀 Deployment

### Docker Compose — Local / Staging

```bash
# 1. Clone and configure
git clone https://github.com/OmarAbdelhamidAly/OpenQ.git
cd OpenQ
cp .env.example .env
# Edit .env — minimum required: GROQ_API_KEY, OPENROUTER_API_KEY, SECRET_KEY, AES_KEY

# 2. Launch all 22 services
docker compose up --build -d

# 3. Verify
docker compose ps
curl http://localhost:8002/health
```

**Services started:**

| Container | Port | Role |
|---|---|---|
| `analyst-api` | 8002 | API Gateway + Glassmorphism SPA |
| `analyst-governance` | — | Governance worker |
| `analyst-worker-sql` | — | SQL analysis (12-node) |
| `analyst-worker-csv` | — | CSV analysis (11-node) |
| `analyst-worker-json` | — | JSON analysis (10-node) |
| `analyst-worker-pdf` | — | PDF RAG (10-node, Gemini 2.0 Flash) |
| `analyst-worker-code` | — | Codebase analysis (8-node, Neo4j) |
| `analyst-worker-audio` | — | Audio intelligence (Gemini 1.5 Flash) |
| `analyst-worker-image` | — | Image analysis (Gemini multimodal) |
| `analyst-video` | — | Video analysis (Gemini) |
| `analyst-corporate` | 8009 | Org-Tree & Task Governance |
| `analyst-exporter` | — | Export service (PDF/XLSX/JSON) |
| `analyst-postgres` | 5433 | Metadata database |
| `analyst-redis` | 6379 | Broker + cache + HITL checkpoints |
| `analyst-qdrant` | 6333 | Vector database |
| `analyst-neo4j` | 7474/7687 | Knowledge graph |
| `analyst-mongodb` | 27017 | JSON document store |
| `analyst-prometheus` | 9090 | Metrics collection |
| `analyst-grafana` | 3000 | Monitoring dashboards |
| `analyst-flower` | 5555 | Celery task monitoring |
| `analyst-frontend` | 3001 | Standalone React/Vite UI |

### Kubernetes — Production (AWS EKS)

Manifests are organized in numbered apply-order directories targeting two namespaces:
`openq-core` (API Gateway, Frontend, Governance, Exporter) and `openq-workers` (all Celery pillar workers).

```bash
# Step 1 — Namespaces
kubectl apply -f k8s/01-namespaces.yaml

# Step 2 — ConfigMap + Secrets
kubectl apply -f k8s/02-config.yaml

# Step 3 — Core services (API Gateway + Frontend)
kubectl apply -f k8s/03-core/

# Step 4 — Worker deployments (all pillar workers)
kubectl apply -f k8s/04-workers/

# Step 5 — AWS ALB Ingress
kubectl apply -f k8s/05-ingress/alb-ingress.yaml
```

> **Tip:** To provision the AWS infrastructure (VPC, EKS, Aurora, ElastiCache, ECR) before deploying manifests, run Terraform first — see [Terraform section](#terraform--aws-infrastructure) below.

---

## ⚡ Getting Started

### Prerequisites

- Docker + Docker Compose v2
- [OpenRouter API key](https://openrouter.ai) (free tier available)
- [Groq API key](https://console.groq.com) (free tier)
- [Gemini API key](https://aistudio.google.com) (free tier)
- 8 GB RAM recommended (4 GB minimum for local, 16 GB for all workers)

### Quick Start

```bash
git clone https://github.com/OmarAbdelhamidAly/OpenQ.git
cd OpenQ
cp .env.example .env
```

Edit `.env`:

```bash
OPENROUTER_API_KEY=sk-or-...
GROQ_API_KEY=gsk_...
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
AES_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
```

```bash
docker compose up --build -d
```

Open **http://localhost:8002** → Register → Upload a data source → Ask a question.

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
| `OPENROUTER_API_KEY` | OpenRouter API key — primary LLM gateway |
| `GROQ_API_KEY` | Groq fallback — `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | Gemini Direct fallback + PDF Vision synthesis |
| `SECRET_KEY` | 64-char random hex for JWT signing (local/dev) |
| `AES_KEY` | Base64-encoded 32-byte key for SQL credential encryption |
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |

### Per-Pillar LLM Model Variables

Each worker can use a different model, configured independently:

| Variable | Production Default | Pillar |
|---|---|---|
| `LLM_MODEL` | `google/gemini-2.0-flash-001` | Default (CSV, JSON, Governance) |
| `LLM_MODEL_SQL` | `google/gemini-2.0-flash-001` | SQL pillar — high accuracy |
| `LLM_MODEL_PDF` | `google/gemini-2.0-flash-lite-001` | PDF pillar — cost optimised |
| `LLM_MODEL_CODE` | `deepseek/deepseek-chat-v3-0324` | Code pillar — code-native LLM |
| `LLM_MODEL_NEXUS` | `google/gemini-2.0-flash-001` | Nexus synthesis |
| `LLM_MODEL_FAST` | `meta-llama/llama-3.2-3b-instruct` | Audio/video metadata |
| `LLM_MODEL_VISION` | `meta-llama/llama-3.2-11b-vision-instruct` | Image/video vision |

### Authentication Variables

| Variable | Development | Production |
|---|---|---|
| `AUTH_STRATEGY` | `jwt` (local) | `auth0` |
| `AUTH0_DOMAIN` | — | `<your-tenant>.auth0.com` |
| `AUTH0_AUDIENCE` | — | `https://analyst-api.com` |
| `AUTH0_CLIENT_ID` | — | Auth0 application client ID |

> In production (`ENV=production`), the platform switches to **Auth0** for enterprise-grade SSO and MFA. Local development uses the built-in JWT strategy.

### Optional Infrastructure Variables

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | Set to `production` to enforce secret validation + hide Swagger docs |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum file upload size |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt connection string |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | — | Neo4j password |
| `MONGO_URI` | `mongodb://mongodb:27017` | MongoDB connection string |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB URL |
| `SQLITE_BASE_DIR` | `/tmp/tenants` | Base directory for tenant uploaded files |

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
| **PDF / Image / Video Vision** | Gemini 2.0 Flash Vision (Multimodal) | Latest |
| **Audio Analysis** | Gemini 1.5 Flash (OpenRouter) | Latest |
| **Task Queue** | Celery + Redis (`AsyncRedisSaver` for HITL) | 5.4.0 |
| **Primary Database** | PostgreSQL 16 + SQLAlchemy async | 2.0.36 |
| **Vector Database** | Qdrant (768d — JSON RAG + PDF embeddings) | Latest |
| **Knowledge Graph** | Neo4j (code AST + cross-pillar entities) | Latest |
| **Document Store** | MongoDB (JSON pipeline aggregations) | Latest |
| **Authentication** | JWT (python-jose) + bcrypt + Redis JTI blacklist | Latest |
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

## ☁️ Terraform — AWS Infrastructure

The `terraform/` directory provisions the complete AWS cloud infrastructure from scratch:

```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# After apply, configure kubectl:
aws eks update-kubeconfig --region us-east-1 --name openq-eks-cluster
```

| Module | AWS Resource | Details |
|---|---|---|
| `vpc` | VPC + Subnets + NAT | CIDR `10.0.0.0/16`, public + private subnets |
| `eks` | EKS Cluster | `openq-eks-cluster`, `t3.large` worker nodes |
| `database` | Aurora Serverless v2 | PostgreSQL-compatible, 0.5–2.0 ACUs (auto-scales to zero) |
| `cache` | ElastiCache Redis | Managed Redis — Celery broker + HITL checkpoints |
| `ecr` | Elastic Container Registry | Stores all `omarabdelhamidaly/openq-*` Docker images |
| `iam-cicd` | IAM Role + Policy | Least-privilege role for GitHub Actions / CI pipeline |

**Terraform outputs:**
```
vpc_id                 → VPC resource ID
eks_cluster_endpoint   → Kubernetes API endpoint
aurora_db_endpoint     → PostgreSQL connection host
redis_primary_endpoint → Redis connection host
kubeconfig_command     → aws eks update-kubeconfig ... command
```

---

## 🎬 Demo

> **Business Demo Video** available — produced with Pippit AI.
> See [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the full script and voiceover used.

---

<div align="center">

**NTI Final Capstone Project — National Telecommunication Institute, Egypt**

*420-hour intensive program in multi-agent systems, RAG pipelines, and LLM orchestration*

Built by a team of AI engineers committed to production-grade, enterprise-ready systems.

> An open, composable alternative to **Amazon Q Business** — designed for any organization sitting on fragmented multi-modal, multi-format enterprise data.

⭐ If this project helped you, please star the repository.

**Full Architecture Documentation:**
- 🏛️ [Architecture Deep-Dive](NTI_ARCHITECTURE.md) — Clean Architecture, all 9 LangGraph pipelines, security, deployment
- 📐 [C4 Diagrams](NTI_C4_DIAGRAMS.md) — Context → Container → Component → Code level diagrams
- 📡 [API Documentation](NTI_API_DOCUMENTATION.md) — All endpoints, request/response schemas, RBAC table

</div>
