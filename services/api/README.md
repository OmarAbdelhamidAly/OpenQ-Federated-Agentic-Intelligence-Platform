<div align="center">

# 🌐 API Gateway (Layer 1)

**Secure, Multi-Tenant Fast API Gateway for OpenQ**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Security](https://img.shields.io/badge/Security-AES--256--GCM-red)](#)

</div>

---

## 🎯 Overview

The `api` service is the Layer 1 Public API Gateway for the OpenQ platform. It acts as the single point of entry for all incoming traffic, shielding the downstream intelligence pillars.

This service NEVER runs analysis execution directly. Instead, it handles request validation, multi-tenant database persistence, authentication state management, and dispatches validated payloads to Celery queues via Redis.

---

## 🏗️ Architecture Design

### Core Modules
- **Authentication (`routers/auth.py`)**: Hands out JWT tokens (30m access, 7d refresh) during local development, or proxies to Auth0 in production mode (`AUTH_STRATEGY=auth0`). Handles Redis-backed JTI revocation.
- **Tenant Isolation**: Achieved natively in SQLAlchemy. The `get_current_user` FastAPI dependency extracts the `tenant_id` from the token and injects it into every core database read/write query context.
- **SQL Guardrails (`infrastructure/sql_guard.py`)**: Implements strict three-layer validation for SQL DB strings and payloads: SELECT-only enforcement, regex blocklists for DML operations, and LLM semantic validation handoffs.
- **Encryption Adapter (`encryption.py`)**: Symmetrically encrypts remote data source credentials (e.g., PostgreSQL credentials from user inputs) using AES-256-GCM before writing to the database.

### Self-Healing Data Migrations
The `lifespan` context manager natively acquires a PostgreSQL advisory lock upon startup and performs idempotent schema validations (`CREATE TABLE IF NOT EXISTS`, etc.). This guarantees zero-downtime evolution in Kubernetes without requiring massive external Alembic rollout procedures.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async connection string to PostgreSQL 16. |
| `REDIS_URL` | Redis instance for rate limiting and JWT blacklisting. |
| `SECRET_KEY` | 64-char hex key for signing JWTs. |
| `AES_KEY` | Base64-encoded 32-byte key for credential encryption. |
| `AUTH_STRATEGY` | `jwt` (local) or `auth0` (production). |
| `CORS_ORIGINS` | JSON array of permitted Frontend IPs/Domains. |
| `ENV` | `development` or `production`. |

---

## 🚀 Queues & Task Dispatch
The API gateway dispatches heavy processing to the `CELERY_BROKER`:
- Governance Analysis: `app.send_task(...)` pushed to the intake nodes.
- Exporter jobs: Pushed to `services/exporter`.
