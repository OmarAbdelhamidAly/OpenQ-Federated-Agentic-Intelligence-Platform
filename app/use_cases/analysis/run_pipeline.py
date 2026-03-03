"""Analysis Use Case — orchestrates the dispatch of modular pipelines.

Implements Clean Architecture 'Use Case' layer.
Handles lazy loading of modular graphs to ensure team isolation.
"""

from __future__ import annotations

from typing import Any, Dict


def get_pipeline(source_type: str):
    """Return the compiled LangGraph pipeline for the given source type using lazy imports.

    This ensures that:
    1. Team 1 (CSV) code is only loaded when a CSV job is run.
    2. Team 2 (SQL) code is only loaded when a SQL job is run.
    """
    normalised = (source_type or "csv").lower()
    
    if normalised in ("sql", "sqlite", "postgresql", "mysql", "mssql"):
        from app.modules.sql.workflow import sql_pipeline
        return sql_pipeline
    
    # Default to CSV pipeline
    from app.modules.csv.workflow import csv_pipeline
    return csv_pipeline
