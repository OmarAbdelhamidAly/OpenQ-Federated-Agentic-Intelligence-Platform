# Autonomous Data Analyst - Technical Documentation

This document outlines the architecture, internal workflows, data flow, and components of the Autonomous Data Analyst SaaS platform.

For a focused guide on the administrator experience, see the [Admin User Flow](ADMIN_FLOW.md).

---

## 1. System Architecture (Clean Architecture)

The application follows a **Modular Clean Architecture** pattern, ensuring strict separation of concerns:

- **Entities (`app/domain/`)**: The innermost business logic and shared state definitions (`AnalysisState`).
- **Use Cases (`app/use_cases/`)**: Cross-modular orchestrators (e.g., Analysis, Auto-Analysis, Export) that lazy-load modular pipelines.
- **Modules (`app/modules/`)**: Self-contained feature sets with exhaustive internal documentation.
- **Infrastructure (`app/infrastructure/`)**: Low-level adapters for DBs, Redis, vectors (Qdrant), and encryption.

---

## 2. Team-Based Development & Ownership

The project is designed for parallel development using **Exhaustive Documentation Packages**:

### 🟢 Team 1: CSV Module (`app/modules/csv/`)
-   **Documentation**: Includes a [DEVELOPER_GUIDE.md](app/modules/csv/DEVELOPER_GUIDE.md) explaining every file and function.
-   **Roadmap**: 10-point plan for advanced features (Forecasting, DuckDB, PII Masking).
-   **Tech**: Pandas, NumPy, IQR Anomaly Detection.

### 🔵 Team 2: SQL Module (`app/modules/sql/`)
-   **Documentation**: Includes a [DEVELOPER_GUIDE.md](app/modules/sql/DEVELOPER_GUIDE.md) detailing security regex and schema discovery.
-   **Roadmap**: 10-point plan for enterprise features (Schema RAG, Query Optimization).
-   **Tech**: SQLAlchemy, Parameterized Queries, Dialect-Agnostic Introspection.

---

## 3. Shared Logic & Bridging Components (`app/modules/shared/`)
-   **Intake Agent**: Standardizes user intent extraction before dispatching to modules.
-   **Output Assembler**: Unifies analysis results into a consistent JSON response for the frontend.
-   **Data Resolvers**: Shared utilities for mapping database IDs to physical file paths or connection strings.

---

## 4. Security & Isolation
-   **Lazy Loading**: Modules are only imported when needed, preventing cross-team dependency conflicts.
-   **SQL Guard**: A strict Regex-based security layer that blocks all non-SELECT/WITH statements.
-   **Tenant Isolation**: Multi-tenant data segregation at the persistence and processing layers.
-   **Credential Encryption**: All external database credentials are encrypted using AES-128 via Fernet.
