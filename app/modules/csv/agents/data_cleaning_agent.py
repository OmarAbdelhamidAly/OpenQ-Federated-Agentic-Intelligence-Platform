"""CSV Pipeline — Data Cleaning Agent.

Handles nulls, deduplication, and dtype fixes for CSV sources.
Runs only when data_quality_score < 0.9.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.adapters.storage import get_tenant_dir


async def data_cleaning_agent(state: AnalysisState) -> Dict[str, Any]:
    """Clean the CSV dataframe: handle nulls, dedup, fix dtypes.

    Only runs when data_quality_score < 0.9.
    SQL sources are never passed to this agent — SQL pipeline has no cleaning step.
    """
    file_path = state.get("file_path")
    if not file_path:
        return {"cleaning_log": ["No CSV file path in state — nothing to clean."]}

    df = pd.read_csv(file_path)
    cleaning_log: List[str] = []

    # 1. Remove exact duplicate rows
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        df = df.drop_duplicates()
        cleaning_log.append(f"Removed {dup_count} duplicate rows.")

    # 2. Handle null values column-by-column
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count == 0:
            continue

        if df[col].dtype in ("float64", "int64"):
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            cleaning_log.append(
                f"Filled {null_count} nulls in '{col}' with median ({median_val})."
            )
        else:
            mode_val = df[col].mode()
            if len(mode_val) > 0:
                df[col] = df[col].fillna(mode_val.iloc[0])
                cleaning_log.append(
                    f"Filled {null_count} nulls in '{col}' with mode ('{mode_val.iloc[0]}')."
                )
            else:
                df[col] = df[col].fillna("Unknown")
                cleaning_log.append(
                    f"Filled {null_count} nulls in '{col}' with 'Unknown'."
                )

    # 3. Attempt datetime parsing on string columns
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.5:
                df[col] = parsed
                cleaning_log.append(f"Parsed '{col}' as datetime.")
        except Exception:
            pass

    # Save cleaned dataframe to tenant directory
    tenant_id = state.get("tenant_id", "unknown")
    tenant_dir = get_tenant_dir(tenant_id)
    clean_path = str(tenant_dir / "cleaned_data.csv")
    df.to_csv(clean_path, index=False)
    cleaning_log.append(f"Saved cleaned data ({len(df)} rows) to {clean_path}.")

    return {
        "clean_dataframe_ref": clean_path,
        "cleaning_log": cleaning_log,
    }
