"""Tool: Profile a DataFrame — schema, types, nulls, unique counts, samples.

CSV Pipeline — reads CSV files via pandas.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    """Input schema for profile_dataframe tool."""
    file_path: str = Field(..., description="Path to the CSV file to profile")


@tool("profile_dataframe", args_schema=ProfileInput)
def profile_dataframe(file_path: str) -> Dict[str, Any]:
    """Profile a CSV file and return schema, types, null counts, unique values, and samples."""
    df = pd.read_csv(file_path)

    columns_info = []
    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "null_pct": round(df[col].isnull().mean() * 100, 2),
            "unique_count": int(df[col].nunique()),
            "sample_values": [str(v) for v in df[col].dropna().head(5).tolist()],
        }

        # Add stats for numeric columns
        if df[col].dtype in ("int64", "float64"):
            col_info["min"] = float(df[col].min()) if not df[col].isnull().all() else None
            col_info["max"] = float(df[col].max()) if not df[col].isnull().all() else None
            col_info["mean"] = round(float(df[col].mean()), 2) if not df[col].isnull().all() else None
            col_info["median"] = float(df[col].median()) if not df[col].isnull().all() else None

        columns_info.append(col_info)

    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_null_cells": int(df.isnull().sum().sum()),
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "columns": columns_info,
    }
