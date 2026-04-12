# 📡 API Documentation

**OpenQ — Autonomous Enterprise Data Intelligence Platform**
Base URL: `http://localhost:8002/api/v1`

All endpoints accept and return `application/json` unless noted.
Protected endpoints require `Authorization: Bearer {access_token}`.

> **Interactive docs (Swagger UI):** `http://localhost:8002/docs` — available in `development` mode only. Disabled in production (`ENV=production`).

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Users](#2-users)
3. [Data Sources](#3-data-sources)
4. [Analysis](#4-analysis)
5. [Knowledge Bases](#5-knowledge-bases)
6. [Policies](#6-policies)
7. [Reports & Export](#7-reports--export)
8. [Metrics](#8-metrics)
9. [Groups](#9-groups)
10. [Voice](#10-voice)
11. [Superset](#11-superset)
12. [Health](#12-health)
13. [Error Responses](#13-error-responses)
14. [Role-Based Access](#14-role-based-access)
15. [Rate Limits Reference](#15-rate-limits-reference)

---

## 1. Authentication

### POST /auth/register

Create a new tenant and its first admin user in a single step.

**Rate limit:** 3 requests / minute per IP

**Request:**
```json
{
  "tenant_name": "Acme Corp",
  "email": "admin@acme.com",
  "password": "SecurePassword123!"
}
```

**Response `201`:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@acme.com",
    "role": "admin",
    "tenant_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "created_at": "2026-03-16T10:00:00Z"
  }
}
```

**Errors:** `400` — Email already registered | `422` — Validation error

---

### POST /auth/login

Authenticate and receive JWT token pair.

**Rate limit:** 5 requests / minute per IP

**Request:**
```json
{
  "email": "admin@acme.com",
  "password": "SecurePassword123!"
}
```

**Response `200`:** Same structure as `/register`.

**Errors:** `401` — Invalid credentials

---

### POST /auth/refresh

Exchange a refresh token for a new token pair. The old refresh token is immediately revoked (rotation prevents token reuse attacks).

**Request:**
```json
{
  "refresh_token": "eyJhbGci..."
}
```

**Response `200`:** New `access_token` + `refresh_token`.

**Errors:** `401` — Expired, invalid, or already-revoked refresh token

---

### POST /auth/logout

**Protected.** Revoke the current refresh token. JTI is added to Redis blacklist — token is dead immediately, before natural expiry.

**Request:**
```json
{
  "refresh_token": "eyJhbGci..."
}
```

**Response `200`:**
```json
{ "message": "Logged out successfully" }
```

---

## 2. Users

### GET /users/me

**Protected.** Return the authenticated user's profile.

**Response `200`:**
```json
{
  "id": "550e8400-...",
  "email": "admin@acme.com",
  "role": "admin",
  "tenant_id": "7c9e6679-...",
  "group_id": "grp-uuid-or-null",
  "created_at": "2026-03-16T10:00:00Z",
  "last_login": "2026-03-20T08:30:00Z"
}
```

---

### POST /users/invite

**Protected · Admin only.** Invite a viewer user to the tenant. Creates the user and returns profile.

**Request:**
```json
{
  "email": "analyst@acme.com",
  "role": "viewer"
}
```

**Response `201`:**
```json
{
  "id": "...",
  "email": "analyst@acme.com",
  "role": "viewer",
  "tenant_id": "..."
}
```

---

### GET /users

**Protected · Admin only.** List all users in the tenant.

**Response `200`:** Array of user objects.

---

## 3. Data Sources

### POST /data-sources/upload

**Protected.** Upload a CSV, XLSX, SQLite, JSON, or PDF file. Triggers automatic schema profiling and background auto-analysis (5 pre-generated insights).

**Request:** `multipart/form-data`
- `file` — The data file
- `name` — Human-readable display name
- `domain_type` (optional) — `"sales" | "hr" | "finance" | "inventory" | "customer"`
- `context_hint` (optional) — Natural language hint about the data context

**Response `201`:**
```json
{
  "id": "ds-uuid",
  "name": "Q4 Sales Data",
  "type": "csv",
  "domain_type": "sales",
  "context_hint": "Contains quarterly sales performance for EMEA region",
  "schema_json": {
    "columns": ["product", "revenue", "quarter"],
    "dtypes": {"product": "object", "revenue": "float64", "quarter": "object"},
    "row_count": 12450,
    "sample_values": {"quarter": ["Q1", "Q2", "Q3", "Q4"]},
    "low_cardinality_values": {"quarter": ["Q1", "Q2", "Q3", "Q4"]}
  },
  "auto_analysis_status": "pending",
  "created_at": "2026-03-20T09:00:00Z"
}
```

---

### POST /data-sources/connect

**Protected · Admin only.** Connect a live SQL database. Credentials are encrypted with AES-256-GCM before storage — the plaintext connection string is never persisted to disk or logs.

**Request:**
```json
{
  "name": "Production CRM",
  "db_type": "postgresql",
  "host": "db.acme.com",
  "port": 5432,
  "database": "crm_prod",
  "username": "readonly_user",
  "password": "...",
  "domain_type": "customer",
  "context_hint": "CRM database with customer orders and shipping data"
}
```

**Response `201`:** Data source object (credentials not returned).

---

### GET /data-sources

**Protected.** List all data sources for the authenticated tenant.

**Response `200`:** Array of data source objects including `auto_analysis_status`.

---

### GET /data-sources/{id}

**Protected.** Retrieve a single data source including schema and auto-analysis status.

---

### GET /data-sources/{id}/auto-analysis

**Protected.** Retrieve the 5 pre-generated analyses computed on upload. Returns immediately if `auto_analysis_status == "done"`.

**Response `200`:**
```json
{
  "status": "done",
  "analyses": [
    {
      "question": "What is the revenue trend over the last 4 quarters?",
      "intent": "trend",
      "insight": "Revenue grew 23% from Q1 to Q4, with Q3 showing the strongest single-quarter jump at +11%.",
      "chart": { "...": "Plotly/ECharts spec" },
      "recommendations": ["Investigate Q3 drivers...", "..."]
    }
  ]
}
```

---

### DELETE /data-sources/{id}

**Protected · Admin only.** Delete a data source and all associated jobs, results, and uploaded files.

---

## 4. Analysis

### POST /analysis/query

**Protected.** Submit a natural-language analysis question. Returns immediately with a `job_id` — use GET /analysis/{job_id} to track progress.

**Request:**
```json
{
  "source_id": "ds-uuid",
  "question": "What are the top 5 products by revenue in Q4?",
  "kb_id": "kb-uuid"
}
```

- `kb_id` (optional) — Link a knowledge base for Gemini multimodal PDF hybrid fusion with SQL results

**Response `202`:**
```json
{
  "job_id": "job-uuid",
  "status": "pending",
  "message": "Analysis queued. Poll /analysis/{job_id} for updates."
}
```

---

### GET /analysis/{job_id}

**Protected.** Poll job status. Surfaces LangGraph `thinking_steps` in real-time and generated SQL for HITL review.

**Response `200` — running:**
```json
{
  "id": "job-uuid",
  "status": "running",
  "intent": "ranking",
  "complexity_index": 3,
  "thinking_steps": [
    {"node": "data_discovery", "status": "completed", "timestamp": "2026-03-20T09:05:01Z"},
    {"node": "analysis_generator", "status": "completed", "timestamp": "2026-03-20T09:05:04Z"}
  ]
}
```

**Response `200` — awaiting admin approval (HITL):**
```json
{
  "id": "job-uuid",
  "status": "awaiting_approval",
  "generated_sql": "SELECT p.name, SUM(s.revenue) AS total FROM sales s JOIN products p ON s.product_id = p.id WHERE s.quarter = 'Q4' GROUP BY p.name ORDER BY total DESC LIMIT 5",
  "message": "Admin approval required before SQL execution against live database."
}
```

**Response `200` — completed:**
```json
{
  "id": "job-uuid",
  "status": "done",
  "completed_at": "2026-03-20T09:05:22Z"
}
```

---

### POST /analysis/{job_id}/approve

**Protected · Admin only.** Approve a HITL-paused SQL job. Patches the LangGraph state in Redis (`approval_granted: True`) and re-queues the task for resumption from checkpoint.

**Response `200`:**
```json
{ "message": "Job approved and resumed." }
```

**Errors:** `403` — Viewer role | `404` — Job not found | `409` — Job not in `awaiting_approval` state

---

### POST /analysis/{job_id}/reject

**Protected · Admin only.** Reject a HITL-paused SQL job.

**Request:**
```json
{ "reason": "Query touches restricted compensation columns." }
```

**Response `200`:**
```json
{ "message": "Job rejected.", "reason": "Query touches restricted compensation columns." }
```

---

### GET /analysis/{job_id}/result

**Protected.** Retrieve the full analysis result for a completed job.

**Response `200`:**
```json
{
  "job_id": "job-uuid",
  "charts": [
    {
      "type": "bar",
      "engine": "echarts",
      "data": { "...": "ECharts option spec" },
      "viz_rationale": "Bar chart selected for ranking comparison across categorical dimension"
    }
  ],
  "insight_report": "Product A led Q4 with $2.3M in revenue, representing 28% of total quarterly sales. Products B and C showed strong momentum with 15% and 12% quarter-over-quarter growth respectively.",
  "exec_summary": "Top 5 products accounted for 73% of Q4 revenue.",
  "recommendations": [
    "Prioritize Product A inventory for Q1 — demand signals suggest continued growth.",
    "Investigate Product D's 8% Q4 decline relative to Q3 performance.",
    "Run a cohort analysis on new customers acquired via Product C promotions."
  ],
  "data_snapshot": [
    {"name": "Product A", "total": 2300000},
    {"name": "Product B", "total": 1850000}
  ],
  "follow_up_suggestions": [
    "How does Q4 performance compare to the same period last year?",
    "Which regions contributed most to Product A's revenue?"
  ]
}
```

---

### GET /analysis

**Protected.** List all analysis jobs for the authenticated tenant.

**Query parameters:**
- `status` — Filter: `pending | running | done | error | awaiting_approval`
- `source_id` — Filter by data source
- `limit` — Max results (default: 50)
- `offset` — Pagination offset

---

## 5. Knowledge Bases

Knowledge bases link PDF documents to analysis jobs for Gemini 2.0 Flash multimodal hybrid fusion — enriching SQL/CSV results with context from unstructured documents.

### POST /knowledge

**Protected · Admin only.** Create a knowledge base and upload a PDF document. The document is processed and indexed via Gemini 2.0 Flash Vision: pages rendered as images, embeddings stored in Qdrant for semantic retrieval.

**Request:** `multipart/form-data`
- `file` — PDF document
- `name` — Knowledge base name
- `description` — Optional description
- `context_hint` (optional) — Domain hint for better synthesis quality

**Response `201`:**
```json
{
  "id": "kb-uuid",
  "name": "Product Catalog 2026",
  "description": "Official product specifications and pricing",
  "created_at": "..."
}
```

---

### GET /knowledge

**Protected.** List all knowledge bases for the tenant.

---

### DELETE /knowledge/{id}

**Protected · Admin only.** Delete a knowledge base and remove all associated Qdrant vectors.

---

## 6. Policies

Policies are natural-language guardrail rules enforced by the LLM Guardrail Agent before any analysis executes. They are tenant-scoped and loaded per-job.

**Example policies:**
- `"Never expose columns containing 'salary', 'compensation', or 'pay' in query results"`
- `"Reject any query that would return individual employee records"`
- `"Do not allow analysis of the users or auth_tokens tables"`

### POST /policies

**Protected · Admin only.**

**Request:**
```json
{
  "name": "PII Protection",
  "rule": "Never return columns containing personal identifiable information such as SSN, passport number, or date of birth.",
  "is_active": true
}
```

**Response `201`:** Policy object with `id` and `created_at`.

---

### GET /policies

**Protected.** List all policies for the tenant (active and inactive).

---

### PATCH /policies/{id}

**Protected · Admin only.** Update a policy rule or toggle `is_active`.

---

### DELETE /policies/{id}

**Protected · Admin only.**

---

## 7. Reports & Export

### POST /reports/{job_id}/export

**Protected.** Trigger async export of a completed analysis result.

**Request:**
```json
{
  "format": "pdf"
}
```

- `format` — `"pdf" | "xlsx" | "json"`

**Response `202`:**
```json
{
  "report_id": "report-uuid",
  "status": "pending"
}
```

---

### GET /reports/{report_id}

**Protected.** Poll export status.

**Response `200` — ready:**
```json
{
  "report_id": "report-uuid",
  "status": "done",
  "download_url": "/reports/report-uuid/download",
  "expires_at": "2026-03-20T10:00:00Z"
}
```

---

### GET /reports/{report_id}/download

**Protected.** Stream the generated report file. Returns `Content-Disposition: attachment` with appropriate MIME type (`application/pdf`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, or `application/json`).

---

## 8. Metrics

### GET /metrics/summary

**Protected · Admin only.** Tenant-level analytics: job counts by status, average latency, error rate, data source breakdown, intent distribution.

**Response `200`:**
```json
{
  "total_jobs": 847,
  "jobs_by_status": {
    "done": 801,
    "error": 23,
    "awaiting_approval": 8,
    "running": 15
  },
  "avg_completion_seconds": 14.3,
  "data_sources_count": 12,
  "top_intents": {
    "trend": 312,
    "ranking": 198,
    "comparison": 187,
    "correlation": 95,
    "anomaly": 55
  },
  "sources_by_type": {
    "csv": 6,
    "sql": 3,
    "pdf": 2,
    "json": 1
  }
}
```

---

### GET /metrics/jobs

**Protected · Admin only.** Paginated job analytics with per-node latency breakdown.

---

## 9. Groups

Team groups allow organizing users within a tenant for shared data source access and analysis visibility.

### POST /groups

**Protected · Admin only.** Create a new team group.

**Request:**
```json
{
  "name": "Data Science Team",
  "description": "Access to financial and customer data sources"
}
```

**Response `201`:**
```json
{
  "id": "grp-uuid",
  "name": "Data Science Team",
  "tenant_id": "...",
  "created_at": "..."
}
```

---

### GET /groups

**Protected · Admin only.** List all groups in the tenant.

---

### POST /groups/{id}/assign

**Protected · Admin only.** Assign a user to a group.

**Request:**
```json
{ "user_id": "user-uuid" }
```

---

### DELETE /groups/{id}

**Protected · Admin only.** Delete a group and remove user assignments.

---

## 10. Voice

Voice endpoints allow submitting analysis queries via audio input, transcribed server-side before routing through the standard analysis pipeline.

### POST /voice/query

**Protected.** Submit a voice recording for speech-to-text transcription and analysis.

**Request:** `multipart/form-data`
- `file` — Audio file (WAV, MP3, M4A)
- `source_id` — Target data source UUID
- `kb_id` (optional) — Knowledge base UUID for hybrid fusion

**Response `202`:**
```json
{
  "job_id": "job-uuid",
  "transcribed_question": "What are the top 5 products by revenue in Q4?",
  "status": "pending"
}
```

The job proceeds identically to a `POST /analysis/query` after transcription. Use `GET /analysis/{job_id}` to poll status.

---

## 11. Superset

Embeds Apache Superset as an analytics companion for advanced dashboarding alongside OpenQ's agentic analysis.

### GET /superset/embed

**Protected.** Returns an embedded Superset dashboard URL with a pre-authenticated session token.

**Response `200`:**
```json
{
  "embed_url": "http://superset:8088/superset/dashboard/1/?standalone=3",
  "token": "superset-guest-token",
  "expires_at": "2026-03-20T10:00:00Z"
}
```

---

## 12. Health

### GET /health

No authentication required. Returns deep health — verifies PostgreSQL, Redis, and Celery worker connectivity.

**Response `200`:**
```json
{
  "status": "ok",
  "components": {
    "database": "reachable",
    "redis": "reachable",
    "workers": "ready"
  }
}
```

**Response `200` (degraded):**
```json
{
  "status": "degraded",
  "components": {
    "database": "reachable",
    "redis": "error: Connection refused",
    "workers": "ready"
  }
}
```

---

## 13. Error Responses

All errors follow a consistent envelope:

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2026-03-20T09:00:00Z"
}
```

| HTTP Code | Meaning |
|---|---|
| `400` | Bad request — validation or business logic error |
| `401` | Unauthenticated — missing or invalid JWT |
| `403` | Forbidden — authenticated but insufficient role |
| `404` | Resource not found (always tenant-scoped — cannot detect other tenants' resources) |
| `409` | Conflict — e.g. approving a job not in `awaiting_approval` state |
| `413` | Payload too large — file exceeds `MAX_UPLOAD_SIZE_MB` |
| `422` | Unprocessable entity — Pydantic validation failure |
| `429` | Rate limit exceeded |
| `503` | Service unavailable — upstream dependency down |

---

## 14. Role-Based Access

| Endpoint Group | `admin` | `viewer` |
|---|---|---|
| Register / login / refresh / logout | ✅ | ✅ |
| GET /users/me | ✅ | ✅ |
| POST /users/invite | ✅ | ❌ |
| GET /users | ✅ | ❌ |
| POST /data-sources/upload | ✅ | ✅ |
| POST /data-sources/connect | ✅ | ❌ |
| DELETE /data-sources/{id} | ✅ | ❌ |
| GET /data-sources/{id}/auto-analysis | ✅ | ✅ |
| POST /analysis/query | ✅ | ✅ |
| GET /analysis / GET /analysis/{id} | ✅ | ✅ |
| GET /analysis/{id}/result | ✅ | ✅ |
| POST /analysis/{id}/approve | ✅ | ❌ |
| POST /analysis/{id}/reject | ✅ | ❌ |
| POST /knowledge | ✅ | ❌ |
| GET /knowledge | ✅ | ✅ |
| DELETE /knowledge/{id} | ✅ | ❌ |
| POST /policies | ✅ | ❌ |
| GET /policies | ✅ | ✅ |
| PATCH /policies/{id} | ✅ | ❌ |
| DELETE /policies/{id} | ✅ | ❌ |
| GET /metrics/summary | ✅ | ❌ |
| POST /reports/{id}/export | ✅ | ✅ |
| GET /reports/{id}/download | ✅ | ✅ |
| POST /groups | ✅ | ❌ |
| GET /groups | ✅ | ❌ |
| POST /voice/query | ✅ | ✅ |
| GET /superset/embed | ✅ | ✅ |

---

## 15. Rate Limits Reference

| Endpoint | Limit | Enforcement |
|---|---|---|
| `POST /auth/register` | 3 / minute | Per IP (slowapi) |
| `POST /auth/login` | 5 / minute | Per IP (slowapi) |
| All other endpoints | 200 / minute | Per IP (slowapi) |

Rate limit headers returned on every response:
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 187
X-RateLimit-Reset: 1711024860
```

When exceeded, returns `429 Too Many Requests` with a `Retry-After` header.

> **Production note:** Behind a load balancer, trust `X-Forwarded-For` to ensure rate limits are per end-user IP, not per load balancer IP. Configure via `slowapi` `key_func`.
