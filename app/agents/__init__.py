"""Agents package — top-level dispatcher.

Routes to the correct pipeline graph based on source_type:
  - "csv"  → app.agents.csv.graph.csv_pipeline
  - "sql"  → app.agents.sql.graph.sql_pipeline

Usage (e.g. in worker.py):
    from app.agents import get_pipeline
    pipeline = get_pipeline(source_type)
    result = await pipeline.ainvoke(state)
"""

from __future__ import annotations

from app.agents.csv.graph import csv_pipeline
from app.agents.sql.graph import sql_pipeline


def get_pipeline(source_type: str):
    """Return the compiled LangGraph pipeline for the given source type.

    Args:
        source_type: "csv" for CSV/pandas pipeline, anything else for SQL pipeline.

    Returns:
        A compiled LangGraph StateGraph ready to be invoked with AnalysisState.
    """
    normalised = (source_type or "csv").lower()
    if normalised in ("sql", "sqlite", "postgresql", "mysql", "mssql"):
        return sql_pipeline
    return csv_pipeline


# Backward-compat: the old graph.py exported `analysis_pipeline` as a singleton.
# Keep this alias so existing code that did `from app.agents.graph import analysis_pipeline`
# can migrate gradually. New code should use get_pipeline() instead.
analysis_pipeline = None  # Use get_pipeline(source_type) instead.
