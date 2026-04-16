<div align="center">

# 📑 Worker CSV (Tabular Datasets Pillar)

**Flat-file Analysis, Cleaning, and Guardrails**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Pandas](https://img.shields.io/badge/Pandas-2.2-150458?logo=pandas&logoColor=white)](#)

</div>

---

## 🎯 Overview

The `worker-csv` service takes raw CSV or XLSX tabular dataset uploads and seamlessly converts them into intelligent, executive-quality chart dashboards using Pandas and OpenQ's 11-node cyclic state graph infrastructure.

It uniquely handles **Conditional Data Cleaning** logic transparently to the user, ensuring NaN values, malformed dates, and weird encodings are processed cleanly before AI-driven Pandas profiling happens.

---

## 🏗️ Architecture Design

Running dynamically as a scalable `Celery` worker queue instance, it leverages LangChain concepts bound securely in a sandboxed process logic.

### 11-Node Cyclic StateGraph Logic

- **Data Discovery**: Instantiates a DataFrame, inspects `shape`, `dtypes`, null-counts, and basic aggregations.
- **Conditional Cleaning**: Generates a `quality_score`. If score `< 0.9`, it diverts heavily into `data_cleaning` scripts to perform median imputation, standard date casting, and type coercion.
- **Analysis Execution**: The ReAct execution agent acts as a Python computational module. It formulates custom pandas computations (`group_by`, `pivot_table`, `.corr()`).
- **Self-Healing Reflection**: Any Pandas execution error `ValueError`, `KeyError` routes to the correction node with the Traceback, correcting the pandas scripts and re-feeding it up to 3 times.
- **Visualization & Assembly**: Uses execution dataframe blobs to plot interactive structural arrays compatible with frontend presentation libraries like robust Recharts / ECharts UI panels.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Celery broker connectivity endpoint. |
| `DATABASE_URL` | PostgreSQL endpoint to update dataset references. |
| `LLM_MODEL` | Default model for intent planning and pandas script generation. |
| `SQLITE_BASE_DIR` | Absolute path mapping pointing to where the physical `.csv/.xlsx` files are locally uploaded by the API gateways. |

---

## 🚀 Tasks Handled

| Task | Queue | Payload |
|---|---|---|
| `pillar_task` | `pillar.csv` | Standard OpenQ job request configuration. |
