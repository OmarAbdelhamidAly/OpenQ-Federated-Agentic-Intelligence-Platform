# Autonomous Data Analyst - Technical Documentation

This document outlines the architecture, internal workflows, data flow, and components of the Autonomous Data Analyst SaaS platform.

---

## 1. System Architecture

The application follows a modern decoupled architecture:

1. **Frontend SPA:** A Vanilla JavaScript `Single Page Application` communicates with the backend solely via REST APIs using JWT authentication.
2. **FastAPI Backend:** Acts as the gateway. It handles authentication, data source connection requests, database CRUD operations, file uploads, and routes long-running tasks to the asynchronous job queue.
3. **PostgreSQL (App DB):** Stores application state (Users, Tenants, Data Sources encrypted configs, Analysis Jobs, and Caches).
4. **Redis:** Acts as the message broker passing tasks between FastAPI and the Celery Workers.
5. **Celery Worker(s):** Executes the heavy LangGraph workflows. This ensures the FastAPI instances can handle hundreds of concurrent web requests without getting blocked by 30-second AI generation tasks.
6. **Data Storage:** Uploaded CSV/SQLite files are saved to local volume storage (`/app/tenant_data/`). SQL credentials are encrypted via AES symmetric encryption and saved to Postgres.

---

## 2. LLM Agent Framework (LangGraph)

The core "AI Analyst" logic is powered by LangGraph, creating a cyclic graph of specialized "agents" (nodes). The application implements *two distinct graphs* depending on the data source:

### The CSV Pipeline (`app/agents/csv/graph.py`)
Because flat files are unstructured and prone to data quality issues, this pipeline involves data cleaning and Python Sandbox execution.

**Node Execution Flow:**
1. `intake_agent`: Parses the business question and identifies the relevant intent (trend, correlation, comparison) and relevant columns.
2. `data_discovery_agent`: Analyzes the CSV schema, infers data types, samples data, and calculates a `data_quality_score`.
3. *(Conditional)* `data_cleaning_agent`: If the `data_quality_score` is poor, an LLM dictates Pandas data cleaning operations (imputation, string stripping) via an execution tool.
4. `analysis_agent`: Generates a plan and executes a specific Python Sandbox Tool (`run_pandas_query`, `compute_trend`, `compute_correlation`, etc.) to get mathematical answers from the cleaned dataframe.
5. `visualization_agent`: Takes the mathematical answer array/dictionary and generates a robust Plotly schema with dark-glassmorphism styling.
6. `insight_agent`: Writes an executive summary and detailed 3-paragraph report quantifying the findings.
7. `recommendation_agent`: Suggests 2 actionable business steps and 2 follow-up questions.
8. `output_assembler`: Bundles the output of all nodes into the final JSON payload.

### The SQL Pipeline (`app/agents/sql/graph.py`)
Databases are usually governed by rigid types and identity rules. We skip data cleaning and translate questions to standard SQL.

**Node Execution Flow:**
1. `intake_agent`: Parses the question.
2. `data_discovery_agent`: Uses SQLAlchemy Inspector tools to safely extract dialect details, Table Names, Column Types, and Foreign Keys *without* raw query injections.
3. `analysis_agent`: An LLM writes a safe, read-only ANSI standard `SELECT` query utilizing the exact schema discovered in step 2. Executes the query against the remote database using an async connection.
4. `visualization_agent` -> `insight_agent` -> `recommendation_agent` -> `output_assembler` (Identical post-processing logic to the CSV pipeline).

---

## 3. The Auto-Analysis Feature Mechanism

When a user connects a Data Source, they don't want to stare at an empty screen. The Auto-Analysis feature (`app/services/auto_analysis_service.py`) provides an instant "Wow" factor:

1. A user uploads `sales_data.csv`.
2. FastAPI saves the file, inserts the row into the `data_sources` table, and commits the DB transaction.
3. FastAPI fires `BackgroundTasks.add_task(run_auto_analysis, source.id)`. The HTTP response returns `201 Created` instantly.
4. The background task invokes `ChatGroq`. It sends the data schema (first few rows/columns) to the LLM and asks: *"What domain is this data? Generate 5 high-value business questions."*
5. The LLM might return Domain: `Sales` and Questions: `["What is the revenue trend?", "Which region performs best?"]`.
6. The service loops over the 5 questions, directly invoking the `csv_pipeline` graph for each.
7. It aggregates the final charts and insights and saves them directly to the `data_sources.auto_analysis_json` column.
8. The frontend polls for `auto_analysis_status == 'completed'`, and then renders the 5 animated insight cards via the `/dashboard` endpoint.

---

## 4. Security Measures

- **JWT Authentication:** Strict token verification for all endpoints.
- **Tenant Isolation:** Users belong to Tenants. Users can only query Data Sources, Users, and Analysis Jobs belonging to their Tenant ID. Pathing for CSV storage is also `/app/tenant_data/{tenant_id}/`.
- **Database Credential Encryption:** Passwords for remote MySQL/Postgres datastores are never saved in plain text. `app/services/encryption.py` uses AES encryption before DB commit, and decrypts at runtime immediately before establishing the connection pool.
- **Read-Only Safeties:** The SQL pipeline analysis tool strictly searches the generated SQL for `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` and raises a security exception if found, preventing catastrophic data loss attacks.
