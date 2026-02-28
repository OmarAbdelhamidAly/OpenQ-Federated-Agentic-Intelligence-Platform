"""Tool: Clean a DataFrame — handle nulls, dedup, fix dtypes, flag outliers.

CSV Pipeline — operates on CSV files using pandas.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CleanInput(BaseModel):
    """Input schema for clean_dataframe tool."""
    file_path: str = Field(..., description="Path to the CSV file to clean")
    output_path: str = Field(..., description="Path to save the cleaned CSV file")


@tool("clean_dataframe", args_schema=CleanInput)
def clean_dataframe(file_path: str, output_path: str) -> Dict[str, Any]:
    """Clean a CSV DataFrame: remove duplicates, fill nulls, fix dtypes, flag outliers."""
    df = pd.read_csv(file_path)
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
        if df[col].dtype in ("float64", "int64"):
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
    for col in df.select_dtypes(include=["int64", "float64"]).columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        outliers = ((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum()
        if outliers > 0:
            outlier_cols.append(f"{col} ({int(outliers)} outliers)")

    if outlier_cols:
        log.append(f"Outliers detected: {', '.join(outlier_cols)}")

    # Save cleaned data
    df.to_csv(output_path, index=False)
    log.append(f"Saved cleaned data ({len(df)} rows) to {output_path}.")

    return {
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "rows_removed": original_rows - len(df),
        "cleaning_log": log,
        "output_path": output_path,
    }
