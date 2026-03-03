# 🟢 CSV Team: The Ultimate Technical Manual (Exhaustive)

This document is an exhaustive breakdown of **every file** and **every function** in the CSV module. No logic is left unexplained.

---

## 📂 1. Directory Structure Overlook
```text
app/modules/csv/
├── agents/             # The logic (LLM based)
├── tools/              # The workers (Pandas based)
├── workflow.py         # The orchestrator (LangGraph)
└── __init__.py         # Package marker
```

---

## 🕸️ 2. Workflow & Orchestration (`workflow.py`)
This file defines the state machine that powers the CSV analysis.

### Internal Logic Functions:
- **`needs_clarification(state)`**: 
  - Checks if the user's intent is unclear. 
  - If `clarification_needed` is True, it terminates the graph and returns control to the user.
- **`needs_cleaning(state)`**: 
  - Compares `data_quality_score` against a threshold (0.9).
  - Routes the analysis to the `data_cleaning` stage if the score is low.
- **`should_retry(state)`**: 
  - Monitors for errors during processing.
  - Allows the system to "heal itself" by looping back to analysis (Max 3 attempts).
- **`build_csv_graph()`**: 
  - The constructor. It wires all agents together and compiles the final `csv_pipeline` object.

---

## 🤖 3. The Agent Layer (`/agents`)
These are the decision-making components.

- **`__init__.py`**: Mandatory package marker.
- **`analysis_agent.py`**:
  - `analysis_agent()`: Entry function. Handles retry-hints if the previous attempt failed.
  - `_run_csv_analysis()`: Constructs the LLM prompt, extracts the plan.
  - `_dispatch_csv_tool()`: Maps the LLM's chosen "operation" to a specific Python tool.
  - `_parse_json()`: Safely extracts JSON from LLM markdown.
- **`data_cleaning_agent.py`**:
  - `data_cleaning_agent()`: Performs automated data repair (Median/Mode imputation, deduplication, date parsing).
- **`data_discovery_agent.py`**:
  - `data_discovery_agent()`: Performs the initial scan. It computes the row/column counts and the initial "Trust" score of the file.
- **`insight_agent.py`**:
  - `insight_agent()`: Converts data results into a 3-paragraph executive report.
- **`recommendation_agent.py`**:
  - `recommendation_agent()`: Generates 3 actionable business strategies based on the findings.
- **`visualization_agent.py`**:
  - `visualization_agent()`: Generates the Plotly JSON required for the web frontend charts.

---

## 🛠️ 4. The Tool Layer (`/tools`)
The low-level workers that manipulate the CSV files.

- **`__init__.py`**: Mandatory package marker.
- **`clean_dataframe.py`**:
  - `clean_dataframe()`: The core cleaning engine. It uses Median for numbers and Mode for text to fill gaps.
- **`compute_correlation.py`**:
  - `compute_correlation()`: Uses `df.corr()` to find hidden relationships between variables.
- **`compute_ranking.py`**:
  - `compute_ranking()`: Calculates "Top N" items and performs Period-over-Period (PoP) comparisons.
- **`compute_trend.py`**:
  - `compute_trend()`: Performs linear regression to detect increases/decreases.
  - `_compute_single_trend()`: Private helper for trend math and IQR-based anomaly detection.
- **`profile_dataframe.py`**:
  - `profile_dataframe()`: Comprehensive schema profiling (min, max, unique counts).
- **`run_pandas_query.py`**:
  - `run_pandas_query()`: A safe, dispatch-only engine for `groupby`, `filter`, and `pivot` operations.

---

## 🔘 5. Shared Dependencies (`app/modules/shared/`)
-   **`intake_agent.py`**: The gatekeeper.
-   **`output_assembler.py`**: Formats the final results.
-   **`load_data_source.py`**: Resolves the database ID to a physical `.csv` file path.

---

## 🌟 Future Innovation Roadmap (Top 10 Ideas)
1.  **AI Data Augmentation**: Implement a tool that fetches external context (e.g., world weather, exchange rates, or census data) based on CSV column names to enrich analysis.
2.  **Semantic Data Dictionary**: Build a RAG system where users can upload "Business Glossaries." This helps the `analysis_agent` know that `ID_99` actually means `Customer_LTV`.
3.  **DuckDB Integration (Large Files)**: Replace standard Pandas with `DuckDB` for CSVs larger than 1GB to perform SQL-speed operations without high memory overhead.
4.  **Auto-Forecasting Node**: Add a specialized LangGraph node using `Prophet` or `Statsmodels` to provide 12-month projections whenever time-series data is detected.
5.  **Multi-CSV Join Advisor**: Develop an agent that scans multiple uploaded CSVs, detects overlapping ID patterns, and suggests specific `LEFT JOIN` operations to the user.
6.  **Anomaly Root-Cause Analysis**: When the `compute_trend` tool finds an anomaly, trigger a sub-agent to investigate the specific rows and explain *why* it happened (e.g., "This spike was caused by 3 outlier orders in New York").
7.  **Privacy/PII Masking**: Add a pre-processing step to the `data_cleaning_agent` that automatically redacts emails, phones, and names before the sample data is sent to the LLM.
8.  **Automated Feature Engineering**: Create a tool that suggests new calculated columns (e.g., converting "Birth Date" to "Age Group") to provide deeper insights.
9.  **Automated Chart Narrations**: Use a vision-capable LLM to "look" at the generated Plotly charts and provide a one-sentence verbal summary of the visual trend.
10. **CSV-to-SQL Migration Agent**: Build a high-level tool that generates the `CREATE TABLE` and `INSERT` scripts to move messy CSV data into the SQL module's database for permanent storage.
