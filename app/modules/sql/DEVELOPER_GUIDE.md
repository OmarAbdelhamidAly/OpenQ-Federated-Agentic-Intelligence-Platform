# 🔵 SQL Team: The Ultimate Technical Manual (Exhaustive)

This document is an exhaustive breakdown of **every file** and **every function** in the SQL module.

---

## 📂 1. Directory Structure Overlook
```text
app/modules/sql/
├── agents/             # SQL logic generation (LLM based)
├── tools/              # Database drivers (SQLAlchemy based)
├── workflow.py         # The orchestrator (LangGraph)
└── __init__.py         # Package marker
```

---

## 🕸️ 2. Workflow & Orchestration (`workflow.py`)
This file defines the high-integrity pipeline for relational data.

### Internal Logic Functions:
- **`needs_clarification(state)`**: Identifies if the user's question is answerable by the existing database schema.
- **`should_retry(state)`**: The "Auto-Heal" loop. If a syntax error is returned from the DB, the agent is notified and tries to rewrite the SQL (Max 3 attempts).
- **`build_sql_graph()`**: Compiles the `sql_pipeline`. Note: This graph bypasses data cleaning because SQL databases are self-cleaning via constraints.

---

## 🤖 3. The Agent Layer (`/agents`)
The decision-making layers that speak SQL.

- **`__init__.py`**: Mandatory package marker.
- **`analysis_agent.py`**:
  - `analysis_agent()`: Generates the safe SELECT query JSON.
  - `_run_sql_analysis()`: Injects the schema summary into the LLM prompt.
  - `_parse_json()`: Decodes the LLM response into query and parameters.
- **`data_discovery_agent.py`**:
  - `data_discovery_agent()`: The entry point for introspection. It connects to the DB and translates the technical schema into a format context-aware agents can understand.
- **`insight_agent.py`**:
  - `insight_agent()`: Converts database rows into readable business analysis.
- **`recommendation_agent.py`**:
  - `recommendation_agent()`: Generates follow-up strategies based on the SQL data results.
- **`visualization_agent.py`**:
  - `visualization_agent()`: Maps SQL result columns to interactive Plotly charts.

---

## 🛠️ 4. The Tool Layer (`/tools`)
The low-level executors that talk to your database.

- **`__init__.py`**: Mandatory package marker.
- **`run_sql_query.py`**:
  - `run_sql_query()`: The core execution engine.
  - **Security Filter**: Uses a Regex-based filter to kill any non-SELECT commands.
  - **Parameterized Driver**: Uses SQLAlchemy's safe parameter handling to prevent SQL Injection.
- **`sql_schema_discovery.py`**:
  - `sql_schema_discovery()`: Uses the `SQLAlchemy Inspector` to map out tables and foreign keys.
  - **`_quoted()`**: Helper function to ensure table names are correctly escaped for different SQL engines.

---

## 🔘 5. Shared Dependencies (`app/modules/shared/`)
-   **`intake_agent.py`**: Distinguishes between SQL queries and general chat.
-   **`output_assembler.py`**: Bundles the result into a clean API response.
-   **`load_data_source.py`**: Manages the construction and decryption of connection strings.

---

## 🌟 Future Innovation Roadmap (Top 10 Ideas)
1.  **Schema RAG (Vector Table Search)**: Essential for databases with 1000+ tables. Use a Vector DB to index DDLs and retrieve only the most relevant table schemas for each question.
2.  **AI Query Optimizer**: Add a tool that runs `EXPLAIN ANALYZE` on generated queries, detects "Full Table Scans," and automatically suggests missing indexes to the Admin.
3.  **Natural Language DDL / View Management**: Allow "Admin Agents" to safely create materialized views based on frequent user requests to speed up future analysis.
4.  **Cross-Database Virtualization**: Implement a `Multi-DB Connector` (possibly via DuckDB or Apache Calcite) that can JOIN a PostgreSQL table with a MySQL table in one user request.
5.  **Predictive SQL (ML in DB)**: Integrate with frameworks like `PostgresML` to allow the analyst to ask "Predict next month's churn based on this table" using in-database models.
6.  **Data Lineage Visualizer**: Build a tool that generates a diagram showing how columns flow from raw tables through views into the final result set.
7.  **Auto-PII Discovery**: Use a specialized agent to scan table samples for sensitive data (SSN, credit cards) and suggest masking rules for the `visualization_agent`.
8.  **Safe Migration Agent**: A controlled agent that can perform schema updates (e.g., adding a foreign key) based on natural language instructions, with a human-in-the-loop approval step.
9.  **Advanced Relationship Mapping**: Develop logic to crawl table data and find relationships between columns that don't have explicit Foreign Key constraints defined in the DB.
10. **SQL Performance Dashboard**: Create an internal monitoring tool for the team to see which Natural Language questions generate the "Heaviest" or "Slowest" SQL queries.
