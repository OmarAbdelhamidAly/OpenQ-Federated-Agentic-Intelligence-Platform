<div align="center">

# ⚖️ Governance Worker (Layer 2)

**Intake, Intent Classification, and Security Guardrails**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Safety & PII](https://img.shields.io/badge/Security-PII%20Protection-red)](#)

</div>

---

## 🎯 Overview

The `governance` service occupies Layer 2 of the OpenQ architecture. **Every analysis job passes through here first.** It acts as an orchestrating filter between the external `api` limits and the heavy LangGraph execution workers.

No job reaches an execution infrastructure pillar without passing the governance quality gate.

---

## 🏗️ Architecture Design

Running as a scalable Celery worker, this service hosts a specialized LangGraph workflow tailored exclusively for security and routing logic.

```
START → [intake_agent] → check_intake → [guardrail_agent] → route_to_pillar → END
                                │
                                └── clarification_needed → END (rejects/asks to rephrase)
```

### Key Agents

- **Intake Agent**: Scans the incoming natural-language prompt from the user. It extracts entities, assesses ambiguity, assigns a `complexity_index` (from 1-5 to calibrate UI expectations), and explicitly classifies the intent (`trend`, `comparison`, `ranking`, `correlation`, or `anomaly`).
- **Guardrail Agent**: A specialized security LLM module. It pulls the specific Tenant's natural language rules from the PostgreSQL `policies` table and tests the user prompt against them to enforce semantic compliance. For example, if a tenant has a rule "Never reveal executive salaries", the Guardrail Agent will flag any related prompt before SQL or Pandas operations are synthesized. PII scanning also takes place here.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Redis URL for Celery task routing and cache. |
| `DATABASE_URL` | PostgreSQL URL for fetching `policies`. |
| `LLM_MODEL` | Default routing model (e.g. `google/gemini-2.0-flash-001`). |
| `OPENROUTER_API_KEY` | Secure credentials to hit upstream safety models. |

---

## 🚀 Tasks Handled
This worker consumes tasks from the governance queues and dynamically re-routes approved task schemas directly into the respective `pillar.*` queues (`pillar.sql`, `pillar.csv`, etc.) using the built-in Celery router.
