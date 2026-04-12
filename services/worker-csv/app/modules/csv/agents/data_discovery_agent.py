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

    from app.modules.csv.utils.statistics import (
        compute_hurst_exponent, 
        detect_change_points, 
        compute_spectral_seasonality
    )
    from app.modules.csv.utils.ingestion import ingest_csv_to_postgres

    # Generate a unique table name for Superset
    source_id = str(state.get("source_id", "default"))
    table_name = f"csv_{source_id.replace('-', '_')}"

    # Trigger ingestion to Postgres for Superset visualization
    await ingest_csv_to_postgres(file_path, table_name, str(state.get("tenant_id", "default")))

    total_cells = df.shape[0] * df.shape[1]
    null_cells = int(df.isnull().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    # Quality score: penalise nulls and duplicate rows
    null_ratio = null_cells / total_cells if total_cells > 0 else 0
    dup_ratio = duplicate_rows / len(df) if len(df) > 0 else 0
    quality_score = float(round(max(0.0, 1.0 - null_ratio - (dup_ratio * 0.5)), 2))

    columns_info = []
    for col in df.columns:
        series = df[col].dropna()
        info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "null_pct": float(round(df[col].isnull().mean() * 100, 2)),
            "unique_count": int(df[col].nunique()),
            "sample_values": [str(v) for v in series.head(3).tolist()],
        }

        # Add advanced stats for numeric columns
        if pd.api.types.is_numeric_dtype(df[col]) and len(series) >= 20:
            vals = series.values.astype(float)
            hurst = compute_hurst_exponent(vals)
            if hurst is not None:
                info["hurst_exponent"] = round(hurst, 4)
                info["trend_type"] = "trending" if hurst > 0.55 else ("mean-reverting" if hurst < 0.45 else "random-walk")
            
            cp = detect_change_points(vals)
            if cp:
                info["change_points_count"] = len(cp)
            
            season = compute_spectral_seasonality(vals)
            if season.get("period"):
                info["dominant_period"] = season["period"]
                info["seasonal_strength"] = season["strength"]

        columns_info.append(info)

    suggested = _generate_suggested_questions(columns_info)

    schema_summary = {
        "source_type": "csv",
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_rows": duplicate_rows,
        "total_null_cells": null_cells,
        "columns": columns_info,
        "suggested_questions": suggested,
    }

    # ── Neo4j Knowledge Graph Sync (Universal Synthesis Layer) ──────
    try:
        from app.infrastructure.neo4j_adapter import Neo4jAdapter
        neo4j = Neo4jAdapter()
        if source_id:
            # For CSV, we treat the file as a single table
            neo4j.batch_upsert_data_schema(
                source_id=source_id,
                tables=[{
                    "name": table_name,
                    "columns": [{"name": c["name"], "dtype": c["dtype"], "summary": f"Unique: {c['unique_count']}, Null: {c['null_pct']}%"} for c in columns_info]
                }]
            )
            from structlog import get_logger
            get_logger("csv.data_discovery").info("neo4j_csv_schema_sync_done", source_id=source_id)
    except Exception as neo_err:
        from structlog import get_logger
        get_logger("csv.data_discovery").warning("neo4j_csv_sync_failed_secondary", error=str(neo_err))

    return {
        "schema_summary": schema_summary,
        "data_quality_score": quality_score,
        "table_name": table_name,
    }


def _generate_suggested_questions(columns_info: list) -> list[str]:
    """Auto-generate 5 contextual questions strictly based on data types."""
    num_cols = [c["name"] for c in columns_info if "numeric" in c.get("dtype", "").lower() or "int" in c.get("dtype", "").lower() or "float" in c.get("dtype", "").lower()]
    cat_cols = [c["name"] for c in columns_info if "object" in c.get("dtype", "").lower() or "string" in c.get("dtype", "").lower()]
    dt_cols  = [c["name"] for c in columns_info if "datetime" in c.get("dtype", "").lower()]
    
    questions = []
    
    if dt_cols and num_cols:
        questions.append(f"Forecast {num_cols[0]} for the next 30 days")
        questions.append(f"What is the trend of {num_cols[0]} over time?")
        questions.append(f"Are there any anomalies in {num_cols[0]}?")
    
    if cat_cols and num_cols:
        questions.append(f"Show the top 10 {cat_cols[0]} by {num_cols[0]}")
        questions.append(f"Compare {num_cols[0]} across different {cat_cols[0]}")
        
    if len(num_cols) >= 2:
        questions.append(f"What is the correlation between {num_cols[0]} and {num_cols[1]}?")
        
    if not questions:
        questions = ["How many rows are in this dataset?", "What are the columns?"]
        
    return list(dict.fromkeys(questions))[:5]
