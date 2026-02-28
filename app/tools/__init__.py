"""Tools package — re-exports all tools from their new sub-packages for backward compatibility.

New code should import directly from the sub-packages:
    from app.tools.csv.compute_trend import compute_trend
    from app.tools.sql.run_sql_query import run_sql_query

This __init__.py keeps all existing imports working without changes.
"""

# ── CSV Tools ──────────────────────────────────────────────────────────────────
from app.tools.csv.run_pandas_query import run_pandas_query
from app.tools.csv.compute_trend import compute_trend
from app.tools.csv.compute_correlation import compute_correlation
from app.tools.csv.compute_ranking import compute_ranking
from app.tools.csv.clean_dataframe import clean_dataframe
from app.tools.csv.profile_dataframe import profile_dataframe

# ── SQL Tools ──────────────────────────────────────────────────────────────────
from app.tools.sql.run_sql_query import run_sql_query
from app.tools.sql.sql_schema_discovery import sql_schema_discovery

# ── Shared Helpers (not LangChain tools) ──────────────────────────────────────
from app.tools.load_data_source import (
    build_connection_string,
    load_csv,
    resolve_data_path,
    get_connection_string,
    get_source_type,
)

__all__ = [
    # CSV LangChain tools
    "run_pandas_query",
    "compute_trend",
    "compute_correlation",
    "compute_ranking",
    "clean_dataframe",
    "profile_dataframe",
    # SQL LangChain tools
    "run_sql_query",
    "sql_schema_discovery",
    # Shared helpers
    "build_connection_string",
    "load_csv",
    "resolve_data_path",
    "get_connection_string",
    "get_source_type",
]
