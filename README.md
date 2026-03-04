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

## 📂 Project Structure (Clean Architecture)

```text
finalproject/
├── app/
│   ├── domain/                 # INNER CIRCLE: Entities & State (AnalysisState)
│   ├── infrastructure/         # OUTER CIRCLE: DB Adapters, Security, Storage, Constants
│   ├── modules/                # FEATURE MODULES
│   │   ├── csv/                # Squad 1: Spreadsheet Analysis (Isolated)
│   │   ├── sql/                # Squad 2: Relational DB Analysis (Isolated)
│   │   └── shared/             # Shared bridges (Intake, Output, Charts)
│   ├── use_cases/              # APPLICATION LOGIC: Analysts, Auto-Analysis, Exports
│   ├── routers/                # API Endpoints
│   ├── schemas/                # Pydantic models
│   └── static/                 # Frontend SPA (Vanilla JS/CSS/HTML)
├── alembic/                    # Database migrations
├── docker-compose.yml          # Container configuration (FastAPI, Postgres, Redis, Qdrant)
└── DOCUMENTATION.md            # High-level technical overview
```

---

## 👥 Team Workflow & Onboarding

To prevent cross-team interference, the project uses **Exhaustive Module Isolation**. Each team is responsible for their own "feature ecosystem."

### 🟢 1. The CSV Squad (Analysis & Cleaning)
**Focus:** Enhancing Pandas-based logic, data repair, and anomaly detection for flat files.
- **Home Directory:** `app/modules/csv/`
- **Technical Bible:** [CSV Developer Guide](app/modules/csv/DEVELOPER_GUIDE.md) — *Read this before writing any code.*
- **Responsibilities:** Improving the `compute_trend` math, handling messy CSV formats, and implementing the **DuckDB** roadmap.

### 🔵 2. The SQL Squad (Engineering & Security)
**Focus:** High-performance querying, safe schema discovery, and AI security guardrails.
- **Home Directory:** `app/modules/sql/`
- **Technical Bible:** [SQL Developer Guide](app/modules/sql/DEVELOPER_GUIDE.md) — *Read this before writing any code.*
- **Responsibilities:** Schema RAG development, SQL Query Optimization, and ensuring 100% protection against injection.

---

## 📖 Master Documentation (The "Core 6")

1. **[README.md](README.md)**: Project overview and quick start.
2. **[ARCHITECTURE.md](ARCHITECTURE.md)**: Deep-dive into layers, RAG, and security.
3. **[ADMIN_GUIDE.md](ADMIN_GUIDE.md)**: Managing the platform and the handover.
4. **[DEPLOYMENT.md](DEPLOYMENT.md)**: Cost analysis and AWS/Render scaling.
5. **[CSV_TEAM.md](CSV_TEAM.md)**: Technical guide and contract for Team 1.
6. **[SQL_TEAM.md](SQL_TEAM.md)**: Technical guide and contract for Team 2.

---

---

## 🛠️ Developer Workflow & Safety Guardrails

To maintain architectural integrity, this project uses a **Container-Only Workflow**. 

### 1. The Build & Run Ritual
All developers must work inside Docker. This ensures environment parity (your machine vs. production).
```bash
# Start the entire stack
docker compose up --build -d

# Check the heartbeat
docker compose ps
```

### 2. Automated Verification (Safety First)
We have implemented a **GitHub Action** that runs the full test suite in Docker on every Pull Request.
**Do NOT merge your code if the CI badge is Red 🔴.**

To run the tests manually inside the container:
```bash
docker compose exec analyst-worker pytest tests/
```

### 3. Team Isolation Protocol (Preventing Interference)
To ensure Team 1 (CSV) doesn't break Team 2 (SQL):
- **Branch Naming**: Use `csv/feature-name` or `sql/feature-name`.
- **Merge Rules**: You cannot merge to `main` until the CI passes successfully.
- **Module Ownership**: Any changes to `app/modules/shared/` require approval from BOTH team leads.

---

## 🔑 Environment Configuration
The `.env` file is now included in the repository (via `git add -f .env`) to allow immediate setup for the teams. 

> [!WARNING]
> Keep the GROQ API Key and other secrets confidential. If the repository is ever made public, immediately move these to GitHub Secrets and remove the `.env` file from version control.
