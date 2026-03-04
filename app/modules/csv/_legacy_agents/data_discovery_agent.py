"""CSV Pipeline — Data Discovery Agent.

Profiles the CSV data source to build a schema summary and quality score.
Reads the CSV file directly and computes rich column-level statistics.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from app.domain.analysis.entities import AnalysisState


async def data_discovery_agent(state: AnalysisState) -> Dict[str, Any]:
    """Profile the CSV data source and compute a data quality score.

    Populates schema_summary and data_quality_score in state.
    Reads the file directly and computes rich column-level statistics.
    """
    file_path = state.get("file_path")
    if not file_path:
        return {
            "schema_summary": state.get("schema_summary", {}),
            "data_quality_score": 1.0,
        }

    df = pd.read_csv(file_path)

    total_cells = df.shape[0] * df.shape[1]
    null_cells = int(df.isnull().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    # Quality score: penalise nulls and duplicate rows
    null_ratio = null_cells / total_cells if total_cells > 0 else 0
    dup_ratio = duplicate_rows / len(df) if len(df) > 0 else 0
    quality_score = round(max(0.0, 1.0 - null_ratio - (dup_ratio * 0.5)), 2)

    schema_summary = {
        "source_type": "csv",
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_rows": duplicate_rows,
        "total_null_cells": null_cells,
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "null_pct": round(df[col].isnull().mean() * 100, 2),
                "unique_count": int(df[col].nunique()),
                "sample_values": [str(v) for v in df[col].dropna().head(3).tolist()],
            }
            for col in df.columns
        ],
    }

    return {
        "schema_summary": schema_summary,
        "data_quality_score": quality_score,
    }
