# Admin User Flow: End-to-End Guide

This document outlines the complete journey for an **Admin** user within the Autonomous Data Analyst platform. It covers everything from initial organization setup to advanced AI-driven data analysis.

---

## 🏗️ Phase 1: Registration & Tenant Creation
The journey begins at the **Sign Up** tab on the authentication page.

1.  **Organization Setup**: The first user to register for a company provides an **Organization Name** (Tenant). 
2.  **Admin Privileges**: This user is automatically assigned the `admin` role. 
3.  **Authentication**: Upon successful registration, the admin is logged in and redirected to the main Dashboard. 

> [!NOTE]
> The platform is multi-tenant. All data, users, and analysis jobs are strictly isolated within your organization's `tenant_id`.

---

## 📊 Phase 2: Data Source Integration
Admins have exclusive rights to manage data sources. Navigate to the **Data Sources** page from the sidebar.

### Option A: File Upload
- **Supported Formats**: `.csv`, `.xlsx`, `.sqlite`, `.db`, `.sql` (SQL dumps).
- **Process**: Drag and drop a file or use the **Upload File** button.
- **Auto-Profiling**: The system immediately reads the schema (columns, row counts, data types) to prepare for analysis.

### Option B: External SQL Connection
- **Supported Engines**: PostgreSQL, MySQL, MS SQL Server.
- **Process**: Click **Connect SQL** and provide credentials.
- **Security**: Credentials are encrypted at rest using Fernet (AES-128). We recommend using a **Read-Only** database user for maximum safety.

---

## 🧠 Phase 3: AI-Powered Insights
Once a source is added, the **Autonomous Agent** automatically kicks off an initial "Auto-Analysis".

1.  **Status Monitoring**: You will see a ⏳ (Pending) or 🔄 (Running) indicator on the source.
2.  **Source Dashboard**: Once finished, a **Dashboard** button appears.
3.  **Pre-Generated Charts**: Clicking this opens a dashboard with AI-curated charts, executive summaries, and recommended follow-up questions tailored to that specific dataset.

---

## 👥 Phase 4: Team Management
Admins can scale their team by navigating to the **Team Members** page.

1.  **Invite Members**: Click **Invite Member** to add colleagues via email. 
2.  **Role Assignment**:
    -   **Viewer**: Can see dashboards and ask their own questions but cannot add/delete data sources or manage users.
    -   **Admin**: Full access to all administrative features.
3.  **Access Control**: Admins can remove members at any time (except themselves).

---

## 🔍 Phase 5: Advanced Analysis
The **Analysis** page is where the most value is extracted via natural language.

1.  **Ask Questions**: Type questions like *"Who are my top 10 customers by revenue last month?"* or *"Show me the correlation between price and units sold."*
2.  **The Agent Pipeline**:
    -   **SQL Generation**: The agent writes and executes the necessary SQL.
    -   **Visualization**: A relevant Plotly chart is generated dynamically.
    -   **Executive Summary**: A concise business-focused explanation of the results.
    -   **Recommendations**: Practical next steps based on the findings.
3.  **Global History**: Admins can see a history of **all** analysis jobs run by any team member in the organization.

---

## 🛠️ Summary of Admin-Only Features
| Feature | Admin | Viewer |
| :--- | :---: | :---: |
| Upload/Connect Data Sources | ✅ | ❌ |
| Delete Data Sources | ✅ | ❌ |
| Invite/Remove Team Members | ✅ | ❌ |
| View All Organization History | ✅ | ❌ |
| Ask Natural Language Questions | ✅ | ✅ |
| View Pre-Generated Dashboards | ✅ | ✅ |

---

## 🏗️ Phase 6: Clean Architecture & Modular Ownership
The platform follows **Clean Architecture** principles to ensure that **Team 1 (CSV)** and **Team 2 (SQL)** can work in total isolation. Each module now contains its own exhaustive documentation.

### 🏠 The Core (Domain & Infrastructure)
- **`app/domain/`**: The inner-most circle. Contains `AnalysisState` (Entities), the single source of truth.
- **`app/infrastructure/`**: Handles external systems (PostgreSQL, Redis, File System).

### 📦 Modular Features (`app/modules/`)
- **`app/modules/csv/`**: Dedicated to spreadsheet analysis. 
  - **Exhaustivity**: Contains its own `DEVELOPER_GUIDE.md` explaining every line of code.
  - **Innovation**: A 10-point roadmap including **Forecasting (Prophet)** and **DuckDB Integration**.
- **`app/modules/sql/`**: Dedicated to relational databases. 
  - **Exhaustivity**: Contains its own `DEVELOPER_GUIDE.md` detailing security guardrails and schema discovery.
  - **Innovation**: A 10-point roadmap including **AI Query Optimization** and **Schema RAG**.

---

## 🛠️ Phase 7: The Modular Tooling Cabinet
Tools are strictly scoped to prevent cross-team interference.

### 📄 CSV Tools (`app/modules/csv/tools/`)
-   **Core**: `profile_dataframe.py`, `clean_dataframe.py`, `run_pandas_query.py`.
-   **Advanced**: `compute_trend.py` (with IQR anomaly detection), `compute_ranking.py` (with Period-over-Period math), `compute_correlation.py`.

### 🗄️ SQL Tools (`app/modules/sql/tools/`)
-   **Discovery**: `sql_schema_discovery.py` uses SQLAlchemy Inspector for safe Dialect-agnostic probing.
-   **Execution**: `run_sql_query.py` features a **SELECT-only Regex Filter** and 100% parameterized execution.

---

## 🚀 Phase 8: Strategic Roadmap
Admins can oversee the evolution of the platform into an enterprise-grade solution by following the **Innovation Roadmaps** located in each module's `DEVELOPER_GUIDE.md`. The vision is to move from basic querying to predictive, high-performance agentic systems.
