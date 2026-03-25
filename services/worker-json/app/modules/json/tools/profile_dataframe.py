"""Tool: Profile a DataFrame — schema, types, nulls, unique counts, samples.

JSON Pipeline — operates on records (list of dicts) from MongoDB results.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    """Input schema for profile_dataframe tool."""
    records: List[Dict[str, Any]] = Field(..., description="List of dicts from MongoDB to profile")


@tool("profile_dataframe", args_schema=ProfileInput)
def profile_dataframe(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Profile JSON/MongoDB records and return schema, types, null counts, unique values, and samples."""
    if not records:
        return {"error": "No records provided for profiling."}

    df = pd.DataFrame(records)

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

        if df[col].dtype in ("int64", "float64", "int32", "float32"):
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
