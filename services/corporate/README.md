# 🏛️ Corporate Strategic Intelligence Service

## 📌 Overview
The **Corporate Service** is the strategic brain of the OpenQ platform. It manages the organizational hierarchy, strategic goals, and compliance policies, ensuring that all AI insights are aligned with the company's core objectives.

---

## 🏗️ Clean Architecture
Following the project's standard, this service is built with a decoupled architecture:
*   **Domain**: Defines `StrategicState` and `CorporateTaskEntity`.
*   **Use Cases**: Core business logic like `AnalyzeSubmissionUseCase` which evaluates employee work against goals.
*   **Infrastructure**: Handles database persistence (`CorporateRepository`) and security (`require_admin` guards).

## 🚀 Key Features
1.  **Organizational Hierarchy**: Multi-level management of departments, branches, and teams.
2.  **Strategic Alignment Agent**: Uses LLMs to analyze if daily tasks contribute to high-level company goals.
3.  **Governance & Policies**: Automated compliance checking for all departmental submissions.
4.  **Admin Dashboard**: A premium interface for executives to visualize the "Strategic Map" of the organization.

## 🔒 Security
*   **RBAC**: Role-Based Access Control is enforced. Only `admin` users can modify hierarchy, goals, or policies.
*   **Multi-Tenancy**: All data is strictly isolated by `tenant_id`.

---

## 🛠️ Tech Stack
- **Framework**: FastAPI
- **Intelligence**: LangChain + OpenAI (OpenRouter)
- **Database**: PostgreSQL (SQLAlchemy 2.0)
