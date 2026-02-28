# Autonomous Data Analyst Agent SaaS

This project is a powerful, full-stack SaaS platform featuring an **Autonomous Data Analyst Agent**. It enables users to upload flat files (CSV) or securely connect external databases (PostgreSQL/MySQL) and ask natural language business questions. 

The backend AI autonomously discovers the schema, generates code or queries (Pandas or SQL), securely executes them, visualizes the results using Plotly, and generates executive summaries with insights and recommendations.

## 🚀 Key Features

- **Multi-Source Support:** Upload `CSV` files or connect securely to remote `PostgreSQL` and `MySQL` databases using encrypted credentials.
- **Auto-Analysis Engine:** Immediately upon connecting a data source, the background worker uses an LLM to detect the data's domain (e.g., Sales, HR, Finance) and generates 5 smart, diverse business questions. It silently runs these questions through the AI pipeline and caches the results.
- **Instant AI Dashboards:** View the results of the auto-analysis on a beautiful, auto-generated Glassmorphism dashboard complete with 5 animated query insight cards and charts.
- **Interactive Q&A:** Submit ad-hoc natural language questions (e.g., "What is the correlation between marketing spend and revenue?"). The system runs the pipeline in real-time, executing sandboxed analysis, and returns a detailed report.
- **Two Distinct AI Pipelines:** 
  - **CSV Pipeline:** Employs LangGraph to orchestrate data discovery, data cleaning, and Python `pandas` query generation in a sandboxed execution environment. 
  - **SQL Pipeline:** Uses LangGraph to orchestrate schema discovery via SQLAlchemy and generates safe, read-only ANSI `SELECT` queries.
- **Robust Background Processing:** Long-running LLM graph pipelines are handled asynchronously using Celery and Redis so the FastAPI thread remains unblocked and responsive.
- **Modern SPA Frontend:** A lightning-fast Vanilla JavaScript Single Page Application featuring a premium Dark Glassmorphism aesthetic, skeleton loaders, and Plotly.js chart animations.

---

## 🛠️ Technology Stack

- **Backend / API**: FastAPI, Uvicorn
- **Database / ORM**: PostgreSQL, SQLAlchemy, Alembic (Migrations)
- **AI Orchestration & LLMs**: LangGraph, Langchain, ChatGroq (Powered by LLaMA-3 70B via Groq API)
- **Data Execution Sandbox**: Pandas (for CSV), SQLAlchemy / asyncpg (for SQL)
- **Task Queue**: Celery & Redis
- **Frontend**: HTML5, Vanilla JavaScript, CSS3 (No heavy UI frameworks)
- **Visualization**: Plotly.js
- **Containerization**: Docker & Docker Compose

---

## � Running the Application Locally (Docker)

The easiest way to run the entire stack (Postgres, Redis, FastAPI backend, and Celery worker) is using Docker Compose.

1. **Clone the repository**
2. **Set up Environment Variables:**
   Create a `.env` file in the root directory and ensure the following variables are set:
   ```env
   # Database & Redis (Docker internal URLs)
   DATABASE_URL=postgresql+asyncpg://analyst:analyst_pass_123@postgres:5432/analyst_db
   REDIS_URL=redis://redis:6379/0

   # Security
   SECRET_KEY=your_super_secret_jwt_key
   ENCRYPTION_KEY=a_32_byte_base64_encryption_key_here

   # AI Provider
   GROCK_API_KEY=gsk_your_groq_api_key_here
   ```
3. **Build and Run:**
   ```bash
   docker compose up --build -d
   ```
4. **Access the Application:**
   Open your browser and navigate to `http://localhost:8000`.

---

## 📂 Project Structure

```
finalproject/
├── app/
│   ├── main.py                 # FastAPI Application entry point
│   ├── worker.py               # Celery Worker entry point
│   ├── core/                   # Config, Security, DB initialization
│   ├── models/                 # SQLAlchemy ORM Tables
│   ├── schemas/                # Pydantic validation models
│   ├── routers/                # API Endpoints (Auth, Users, Data Sources, Analysis)
│   ├── services/               # Encryption, Storage, and Auto-Analysis logic
│   ├── agents/                 # LangGraph AI Workflows Context
│   │   ├── csv/                # Pipeline logic for flat file analysis
│   │   └── sql/                # Pipeline logic for database querying
│   ├── tools/                  # Python functions executed by the LLM (Pandas, DB Connect)
│   └── static/                 # Frontend SPA (Vanilla JS, CSS, HTML)
├── alembic/                    # Database migrations
├── docker-compose.yml          # Container configuration
└── Dockerfile                  # API & Worker Docker build instructions
```

---

## 📚 Further Reading

For a deep dive into the system architecture, LangGraph AI workflows, and data pipeline mechanics, please refer to the `[DOCUMENTATION.md](DOCUMENTATION.md)`.

---

## 👥 Team Workflow & Contribution Guide

This section is specifically for the development team. The engineering team has been split into two core squads to optimize performance without stepping on each other's toes:

### 1. The CSV Squad 📄
**Goal:** Enhance the Pandas-based AI outputs, visualization mapping, and error handling for flat files. The CSV pipeline is prone to data quality issues, so your primary focus is improving the `data_cleaning` and `analysis` agents.

**Your Working Directory:** `app/agents/csv/` and `app/tools/csv/`

**Your Specific Tasks & Responsibilities:**
1. **Improve Pandas Code Generation:** Update `analysis_agent.py` to handle complex multi-step user questions (e.g., merging generated dataframes, pivoting data).
2. **Add More CSV Tools:** Currently, we have `compute_trend` and `run_pandas_query`. Your task is to build more specific tools like `compute_anomaly`, `forecast_timeseries`, and `segment_customers` inside `app/tools/csv/`.
3. **Data Cleaning Enhancements:** Improve `data_cleaning_agent.py` so it can automatically detect and drop extreme outliers or normalize weird date string formats before analysis begins.

**Rules of Engagement:** 
- **Branching:** You MUST work exclusively on a branch prefixed with `csv/` (e.g., `csv/add-anomaly-tool`).
- You may only modify files within your directory.
- You are responsible for ensuring `graph.py` inside the `csv/` folder successfully transforms raw user strings into Pandas code.
- DO NOT merge your own code to `main`. Open a Pull Request for the Team Lead to review and merge manually.

### 2. The SQL Squad 🗄️
**Goal:** Optimize complex database querying, SQLAlchemy discovery speed, and the accuracy of the ANSI SQL generation while prioritizing absolute security against SQL injections.

**Your Working Directory:** `app/agents/sql/` and `app/tools/sql/`

**Your Specific Tasks & Responsibilities:**
1. **Advance SQL Generation:** Update `analysis_agent.py` to write advanced SQL queries utilizing `CTEs`, `Window Functions`, and `JOINs` across 5+ tables without hallucinating phantom columns.
2. **Implement Smart Schema Caching:** Update the schema discovery logic so that if a database has 500 tables, the LLM only receives the schema for the 5 tables relevant to the user's specific question (to save LLM token costs).
3. **Strict Query Validations:** Enhance the SQL execution tool to rigorously block `DROP`, `DELETE`, or `UPDATE` commands. Ensure errors from the DB are caught and fed back to the LLM for self-correction.

**Rules of Engagement:** 
- **Branching:** You MUST work exclusively on a branch prefixed with `sql/` (e.g., `sql/schema-caching`).
- You may only modify files within your directory.
- You are responsible for ensuring the `analysis_agent.py` generates 100% read-only queries with strict enforcement.
- DO NOT merge your own code to `main`. Open a Pull Request for the Team Lead to review and merge manually.

### 🛡️ Deployment & Merge Strategy
To prevent the CSV squad from breaking the SQL squad's code (and vice versa):
1. Both teams must work on **isolated branches**.
2. When a feature is complete, open a **Pull Request (PR)** targeting the `main` branch.
3. The GitHub Actions pipeline will only run a basic **syntax linter (flake8)** to ensure there are no missing imports or major Python typos.
4. **The Team Lead is the only person authorized to press "Merge".** They will pull the branch locally, test the AI pipeline manually, and then merge the code into `main` if it passes.
