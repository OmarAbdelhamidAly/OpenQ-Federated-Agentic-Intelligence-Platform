# 📡 API Documentation

**DataAnalyst.AI — Autonomous Enterprise Data Analyst**
Base URL: `http://localhost:8002/api/v1`

All endpoints accept and return `application/json` unless noted. Protected endpoints require `Authorization: Bearer {access_token}`.

API docs (Swagger UI) available at `http://localhost:8002/docs` in development mode. Hidden in production (`ENV=production`).

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
9. [Health](#9-health)
10. [Error Responses](#10-error-responses)
11. [Role-Based Access](#11-role-based-access)

---

## 1. Authentication

### POST /auth/register

Create a new tenant and its first admin user.

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
    "created_at": "2025-03-16T10:00:00Z"
  }
}
```

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

**Errors:**
- `401` — Invalid email or password

---

### POST /auth/refresh

Exchange a refresh token for a new token pair. The old refresh token is immediately revoked (rotation).

**Request:**
```json
{
  "refresh_token": "eyJhbGci..."
}
```

**Response `200`:** New `access_token` + `refresh_token`.

**Errors:**
- `401` — Expired, invalid, or already-revoked refresh token

---

### POST /auth/logout

Revoke the refresh token immediately. The access token expires naturally after 30 minutes.

**Request:**
```json
{
  "refresh_token": "eyJhbGci..."
}
```

**Response `204`:** No content.

---

## 2. Users

### GET /users/me

Get the current authenticated user's profile.

**Headers:** `Authorization: Bearer {access_token}`

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "admin@acme.com",
  "role": "admin",
  "tenant_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "created_at": "2025-03-16T10:00:00Z",
  "last_login": "2025-03-16T12:30:00Z"
}
```

---

### POST /users/invite

**Admin only.** Invite a new user to the tenant.

**Request:**
```json
{
  "email": "analyst@acme.com",
  "role": "viewer"
}
```

**Response `201`:** New user object with temporary password.

---

### GET /users

**Admin only.** List all users in the tenant.

**Response `200`:**
```json
{
  "users": [
    {"id": "...", "email": "admin@acme.com", "role": "admin", ...},
    {"id": "...", "email": "analyst@acme.com", "role": "viewer", ...}
  ]
}
```

---

## 3. Data Sources

### POST /data-sources/upload

Upload a CSV, XLSX, or SQLite file. Triggers automatic schema profiling and background auto-analysis.

**Headers:** `Authorization: Bearer {access_token}` + `Content-Type: multipart/form-data`

**Form fields:**
- `file` (required) — The file to upload
- `name` (required) — Display name for the data source

**Response `201`:**
```json
{
  "id": "a3f8b2c1-...",
  "type": "csv",
  "name": "Q4 Sales Data",
  "schema_json": {
    "columns": [
      {
        "name": "revenue",
        "dtype": "float64",
        "null_count": 0,
        "unique_count": 847,
        "sample_values": [12500.0, 8300.0, 15200.0]
      }
    ],
    "row_count": 5000,
    "column_count": 12
  },
  "auto_analysis_status": "pending",
  "domain_type": "sales",
  "created_at": "2025-03-16T10:05:00Z"
}
```

**Auto-analysis:** After upload, the system automatically generates 5 analysis questions, runs them in the background, and stores results in `auto_analysis_json`. These are immediately available on the UI without any user action.

---

### POST /data-sources/connect-sql

Connect a PostgreSQL or MySQL database. Credentials are encrypted with AES-256 before storage.

**Request:**
```json
{
  "name": "Production DB",
  "host": "db.acme.com",
  "port": 5432,
  "database": "analytics",
  "username": "readonly_user",
  "password": "db_password",
  "db_type": "postgresql"
}
```

**Response `201`:** Data source object. Credentials are never returned after creation.

---

### GET /data-sources

List all data sources for the tenant.

**Response `200`:**
```json
{
  "sources": [
    {
      "id": "a3f8b2c1-...",
      "type": "csv",
      "name": "Q4 Sales Data",
      "row_count": 5000,
      "auto_analysis_status": "done",
      "domain_type": "sales",
      "created_at": "2025-03-16T10:05:00Z"
    }
  ]
}
```

---

### GET /data-sources/{source_id}

Get a single data source with full schema details.

---

### DELETE /data-sources/{source_id}

**Admin only.** Delete a data source and all associated analysis jobs.

**Response `204`:** No content.

---

## 4. Analysis

### POST /analysis/query

Submit a natural-language analysis question. Creates a pending job and dispatches it through the 4-layer pipeline.

**Request:**
```json
{
  "source_id": "a3f8b2c1-...",
  "question": "What are the top 5 products by revenue in Q4?",
  "kb_id": null,
  "complexity_index": 2,
  "total_pills": 1
}
```

| Field | Type | Description |
|---|---|---|
| `source_id` | UUID | The data source to analyze |
| `question` | string | Natural language question |
| `kb_id` | UUID (optional) | Knowledge base for PDF hybrid fusion |
| `complexity_index` | int 1-5 | Complexity hint from intake agent |
| `total_pills` | int | Number of analysis sub-questions |

**Response `201`:**
```json
{
  "id": "b5e2a1f3-...",
  "status": "pending",
  "question": "What are the top 5 products by revenue in Q4?",
  "source_id": "a3f8b2c1-...",
  "created_at": "2025-03-16T10:10:00Z"
}
```

**Job lifecycle:**
```
pending → running → awaiting_approval (SQL only) → running → done
                                                           └→ error
```

---

### GET /analysis/{job_id}

Poll the status of an analysis job. Poll every 2-3 seconds until `status=done`.

**Response `200`:**
```json
{
  "id": "b5e2a1f3-...",
  "status": "awaiting_approval",
  "question": "What are the top 5 products by revenue in Q4?",
  "generated_sql": "SELECT product_name, SUM(revenue) as total_revenue FROM sales WHERE quarter = 'Q4' GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5",
  "thinking_steps": [
    {"node": "data_discovery", "output": "Found 12 columns, 5000 rows..."},
    {"node": "analysis_generator", "output": "Generated SELECT query..."}
  ],
  "retry_count": 0,
  "started_at": "2025-03-16T10:10:02Z"
}
```

When `status=awaiting_approval`, the `generated_sql` is shown to the admin for review before execution.

---

### POST /analysis/{job_id}/approve

**Admin only.** Approve a paused SQL job. Updates LangGraph checkpointer state and re-dispatches to the SQL worker.

**Response `200`:** Updated job with `status=running`.

---

### GET /analysis/{job_id}/result

Get the full analysis result for a completed job.

**Response `200`:**
```json
{
  "job_id": "b5e2a1f3-...",
  "charts": [
    {
      "type": "bar",
      "data": {...},
      "layout": {"title": "Top 5 Products by Revenue Q4"}
    }
  ],
  "insight_report": "Product A dominated Q4 with $2.3M in revenue, representing 34% of total sales. Products B and C showed strong growth momentum (+18% vs Q3). The bottom 2 performers account for only 8% of revenue and may warrant strategic review.",
  "recommendations": [
    "Increase inventory allocation for Product A ahead of Q1 demand",
    "Investigate the sales velocity drop for Products D and E",
    "Consider bundling Products B and C given their co-purchase correlation"
  ],
  "data_snapshot": [
    {"product_name": "Product A", "total_revenue": 2300000},
    ...
  ]
}
```

---

### GET /analysis/history

Get analysis job history.

**Query params:**
- `limit` (default 50, max 200)
- `offset` (default 0)

**Access control:**
- **Admin:** sees ALL jobs for the tenant
- **Viewer:** sees ONLY their own jobs

---

### POST /analysis/diagnose

Analyze a business problem and suggest diagnostic scenarios before submitting a full query.

**Request:**
```json
{
  "source_id": "a3f8b2c1-...",
  "problem_description": "Our customer churn rate increased by 15% last quarter"
}
```

**Response `200`:**
```json
{
  "suggested_analyses": [
    "Which customer segments have the highest churn rate?",
    "What is the correlation between support tickets and churn?",
    "How does churn vary by subscription duration?"
  ],
  "detected_intent": "anomaly",
  "schema_context": "Relevant columns: customer_id, churn_date, segment, tenure_months"
}
```

---

## 5. Knowledge Bases

### POST /knowledge

Upload a PDF and index it in Qdrant for hybrid SQL+PDF fusion.

**Form fields:**
- `file` — PDF file
- `name` — Knowledge base name
- `description` — Optional description

**Response `201`:** Knowledge base object with indexing status.

---

### GET /knowledge

List all knowledge bases for the tenant.

---

### DELETE /knowledge/{kb_id}

**Admin only.** Delete knowledge base and all Qdrant vectors.

---

## 6. Policies

Admin-managed guardrail rules enforced by the Governance layer before any analysis executes.

### POST /policies

**Admin only.** Create a new guardrail policy.

**Request:**
```json
{
  "name": "No PII Exposure",
  "rule": "Never generate queries that expose columns containing email, phone, SSN, or credit card data",
  "is_active": true
}
```

---

### GET /policies

List all active policies for the tenant.

---

### PATCH /policies/{policy_id}

Update or deactivate a policy.

---

## 7. Reports & Export

### POST /reports/export/{job_id}

Trigger async export of an analysis result.

**Request:**
```json
{
  "format": "pdf"
}
```

Supported formats: `pdf`, `xlsx`, `json`

**Response `202`:** Export job ID. Poll `/reports/export/{export_id}/status` for completion.

---

### GET /reports/export/{export_id}/download

Download the exported file once status is `done`.

**Response:** Binary file with appropriate `Content-Type` header.

---

## 8. Metrics

### GET /metrics/usage

**Admin only.** Tenant usage statistics.

**Response `200`:**
```json
{
  "total_jobs": 147,
  "jobs_this_month": 43,
  "avg_latency_ms": 8420,
  "jobs_by_status": {
    "done": 138,
    "error": 6,
    "pending": 3
  },
  "jobs_by_source_type": {
    "csv": 89,
    "sql": 58
  }
}
```

---

### GET /metrics/jobs

Time-series job completion data for dashboard charts.

---

## 9. Health

### GET /health

**No authentication required.** Liveness probe.

**Response `200`:**
```json
{"status": "ok"}
```

---

## 10. Error Responses

All errors return a consistent structure:

```json
{
  "detail": "Human-readable error message"
}
```

| Code | Meaning |
|---|---|
| `400` | Bad request — invalid input |
| `401` | Unauthorized — missing or invalid/expired token |
| `403` | Forbidden — insufficient role (admin required) |
| `404` | Not found — resource doesn't exist or belongs to another tenant |
| `409` | Conflict — email already registered |
| `422` | Validation error — missing required field or wrong type |
| `429` | Rate limit exceeded |
| `500` | Internal server error — Celery worker failure or DB error |

---

## 11. Role-Based Access

| Endpoint | Admin | Viewer |
|---|---|---|
| Register / Login / Refresh | ✅ | ✅ |
| Upload / Connect data source | ✅ | ❌ |
| List data sources | ✅ | ✅ (own tenant) |
| Submit analysis query | ✅ | ✅ |
| View all jobs | ✅ | ❌ (own only) |
| Approve HITL SQL job | ✅ | ❌ |
| Manage policies | ✅ | ❌ |
| Invite users | ✅ | ❌ |
| View usage metrics | ✅ | ❌ |
| Export results | ✅ | ✅ (own jobs) |
