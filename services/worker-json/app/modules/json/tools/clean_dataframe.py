"""Tool: Clean a DataFrame — handle nulls, dedup, fix dtypes, flag outliers.

JSON Pipeline — operates on records (list of dicts) from MongoDB results.
Returns cleaned records (does NOT write to disk — JSON data lives in MongoDB).
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CleanInput(BaseModel):
    """Input schema for clean_dataframe tool."""
    records: List[Dict[str, Any]] = Field(..., description="List of dicts from MongoDB to clean")


@tool("clean_dataframe", args_schema=CleanInput)
def clean_dataframe(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Clean JSON/MongoDB records: remove duplicates, fill nulls, flag outliers.

    Returns cleaned records and a cleaning log.
    Does NOT write to disk — JSON data is persisted in MongoDB.
    """
    if not records:
        return {"error": "No records provided for cleaning."}

    df = pd.DataFrame(records)
    log: List[str] = []
    original_rows = len(df)

    # 1. Remove duplicates
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        df = df.drop_duplicates()
        log.append(f"Removed {dup_count} duplicate rows.")

    # 2. Handle nulls
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count == 0:
            continue
        if df[col].dtype in ("float64", "int64", "float32", "int32"):
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            log.append(f"Filled {null_count} nulls in '{col}' with median ({median_val}).")
        else:
            mode_vals = df[col].mode()
            fill_val = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unknown"
            df[col] = df[col].fillna(fill_val)
            log.append(f"Filled {null_count} nulls in '{col}' with mode ('{fill_val}').")

    # 3. Flag outliers in numeric columns (IQR method)
    outlier_cols: List[str] = []
    for col in df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        outliers = ((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum()
        if outliers > 0:
            outlier_cols.append(f"{col} ({int(outliers)} outliers)")

    if outlier_cols:
        log.append(f"Outliers detected: {', '.join(outlier_cols)}")

    import json
    cleaned_records = json.loads(df.to_json(orient="records"))

    return {
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "rows_removed": original_rows - len(df),
        "cleaning_log": log,
        "cleaned_records": cleaned_records,
    }
