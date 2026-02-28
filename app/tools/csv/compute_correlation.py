"""Tool: Compute correlation matrix — Pearson or Spearman.

CSV Pipeline — works with CSV files via pandas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CorrelationInput(BaseModel):
    """Input schema for compute_correlation tool."""
    file_path: str = Field(..., description="Path to the CSV file")
    columns: Optional[List[str]] = Field(
        None, description="Specific numeric columns to include (all numeric if None)"
    )
    method: Literal["pearson", "spearman"] = Field(
        "pearson", description="Correlation method"
    )


@tool("compute_correlation", args_schema=CorrelationInput)
def compute_correlation(
    file_path: str,
    columns: Optional[List[str]] = None,
    method: str = "pearson",
) -> Dict[str, Any]:
    """Compute a correlation matrix for numeric columns."""
    df = pd.read_csv(file_path)

    # Select numeric columns
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
        numeric_df = df[valid_cols].select_dtypes(include=["int64", "float64"])
    else:
        numeric_df = df.select_dtypes(include=["int64", "float64"])

    if numeric_df.shape[1] < 2:
        return {"error": "Need at least 2 numeric columns for correlation."}

    corr_matrix = numeric_df.corr(method=method)

    # Find strongest correlations (excluding self-correlation)
    strong_pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i + 1, len(corr_matrix.columns)):
            val = corr_matrix.iloc[i, j]
            if abs(val) > 0.5:
                strong_pairs.append({
                    "column_1": corr_matrix.columns[i],
                    "column_2": corr_matrix.columns[j],
                    "correlation": round(float(val), 4),
                    "strength": "strong" if abs(val) > 0.7 else "moderate",
                })

    return {
        "method": method,
        "matrix": corr_matrix.round(4).to_dict(),
        "columns": list(corr_matrix.columns),
        "strong_correlations": sorted(
            strong_pairs, key=lambda x: abs(x["correlation"]), reverse=True
        ),
    }
