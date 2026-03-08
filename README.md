# DataAnalyst.AI — Premium Autonomous Analytics
**The Enterprise-Grade Autonomous Data Analyst SaaS**

DataAnalyst.AI is a powerful, full-stack platform featuring a sophisticated **Autonomous Data Analyst Agent**. It enables users to upload flat files (CSV) or securely connect massive enterprise databases (PostgreSQL/MySQL) to receive instant, natural-language insights driven by an agentic orchestration layer.

The platform transforms raw data into **Premium Glassmorphism Dashboards** using a production-grade **LangGraph** workflow that includes self-healing query reflection, automated schema discovery, and multi-layer security guardrails.

---

## 🎨 The Premium Experience
- **High-Resolution Visuals**: A custom-engineered CSS layer providing a dark, glassmorphic "Enterprise Command Center" aesthetic with neon accents and floating micro-animations.
- **Micro-Animations**: Animated radial gradients, glowing sidebar states, and interactive stat cards designed to "WOW" stakeholders.
- **Intelligent Reflection**: A system that "thinks" before it acts, visually showing the agent's iterative reasoning process (ReAct) directly in the UI.

---

## 🚀 Strategic Feature Set
- **Recursive Self-Healing**: Utilizing **Zero-Row Reflection** — if a query returns empty results, the agent automatically analyzes the data distribution and re-writes the filter logic without user intervention.
- **Multi-Pipeline Orchestration**:
  - **CSV Pipeline**: Pandas-based analysis with automated data cleaning and anomaly detection.
  - **SQL Pipeline**: Advanced ANSI SELECT generation with schema compression and parallel table profiling.
- **Enterprise Guardrails**: A 3-layer SQL validator using `EXPLAIN` cost analysis and strict security regex to prevent injection or performance degradation.
- **Heterogeneous Intelligence**: Planned roadmap for "Fusion Queries" that join SQL database results with unstructured PDF knowledge bases.
- **Asynchronous Scalability**: Built on **FastAPI**, **Celery**, and **Redis** to handle computationally heavy agentic graphs without blocking the UI.

---

## 🏗️ Technical Architecture
- **Backend / API**: FastAPI, Uvicorn
- **AI Orchestration**: LangGraph, LangChain (LLaMA-3 / Groq)
- **Database / ORM**: PostgreSQL, SQLAlchemy, Qdrant (Vector DB)
- **Frontend**: Vanilla JavaScript (ES9+), CSS3 (Custom Glassmorphism Tier), Plotly.js
- **Infra**: Docker & Docker Compose, Redis (Caching/Queue)

---

## 📂 Project Organization (Clean Architecture)
```text
finalproject/
├── app/
│   ├── modules/
│   │   ├── csv/          # Team 1: Flat-file Analysis & Data Cleaning
│   │   ├── sql/          # Team 2: Enterprise SQL Engineering
│   │   └── shared/       # Shared Agents (Intake, Guardrails, Output)
│   ├── static/           # Premium Frontend SPA (Styles / JS / Assets)
│   └── domain/           # Core Entities (AnalysisState)
├── SQL_TEAM.md           # DEFINITIVE MASTER GUIDE for SQL Engineering
├── CSV_TEAM.md           # Engineering Handbook for CSV Pipeline
└── IMPLEMENTATION_ROADMAP.md # The 17-Point Strategic Vision
```

---

## 📖 Key Documentation
1. **[SQL_TEAM.md](SQL_TEAM.md)**: The "Zero-Loss Detail" guide for the SQL Engineering team.
2. **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)**: The 17-idea roadmap from research papers (DS-STAR / LLM-as-Data-Analyst).
3. **[DEFINITIVE_ARCH_GUIDE.md](DEFINITIVE_ARCH_GUIDE.md)**: Deep-dive into the project's layered architecture.
4. **[DEPLOYMENT.md](DEPLOYMENT.md)**: Production deployment instructions (Docker / K8s).

---

## ⚙️ Quick Start (Docker)
1. **Clone the Repo**
2. **Prepare `.env`**: Ensure `GROCK_API_KEY` and `DATABASE_URL` are set.
3. **Launch Stack**:
   ```bash
   docker compose up --build -d
   ```
4. **Access**: Navigate to `http://localhost:8000` to experience the Premium AI Dashboard.

---
> [!NOTE]
> This project follows the **Master Roadmap**. Every feature addition should be cross-referenced against the Research Synthesis in `SQL_TEAM.md`.
