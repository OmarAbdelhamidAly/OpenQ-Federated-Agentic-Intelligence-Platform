"""Data Discovery Agent for JSON — handles ingestion, stats, and metadata profiling."""

import json
import logging
from typing import Any, Dict, List

import pandas as pd
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.mongo_client import MongoDBClient

logger = logging.getLogger(__name__)

async def data_discovery_agent(state: AnalysisState) -> Dict[str, Any]:
    """Ingest JSON into MongoDB, profile it, and extract schema metadata."""
    file_path = state.get("file_path")
    source_id = str(state.get("source_id", "default"))
    
    if not file_path:
        return {"error": "No file_path provided for JSON discovery."}

    collection_name = f"json_{source_id.replace('-', '_')}"
    table_name = f"json_{source_id.replace('-', '_')}"
    db = MongoDBClient.get_db()
    collection = db[collection_name]

    try:
        # Load raw JSON
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        # Normalize to list of dicts
        data_list = []
        if isinstance(raw_data, dict):
            keys = list(raw_data.keys())
            if len(keys) == 1 and isinstance(raw_data[keys[0]], list):
                data_list = raw_data[keys[0]]
            else:
                data_list = [raw_data]
        elif isinstance(raw_data, list):
            data_list = raw_data
        else:
            data_list = [{"value": raw_data}]

        if not data_list:
            return {"error": "JSON file is empty or invalid format."}

        # 1. Ingest to MongoDB (if not already there)
        count = await collection.count_documents({})
        if count == 0:
            logger.info("ingesting_json_to_mongodb")
            batch_size = 5000
            for i in range(0, len(data_list), batch_size):
                await collection.insert_many(data_list[i:i+batch_size])
            count = len(data_list)
            
        # 2. Flatten for Postgres Ingestion and Stats
        from app.modules.json.utils.json_utils import flatten_json
        flattened_data = flatten_json(data_list)
        df_flattened = pd.DataFrame(flattened_data)
        
        # 3. Profiling and Stats (Mirroring to Postgres removed)

        # 4. Extract schema and compute stats
        from app.modules.json.utils.statistics import (
            compute_hurst_exponent,
            detect_change_points,
            compute_spectral_seasonality
        )
        
        # Quality metrics
        total_cells = df_flattened.shape[0] * df_flattened.shape[1]
        null_cells = int(df_flattened.isnull().sum().sum())
        duplicate_rows = int(df_flattened.duplicated().sum())
        null_ratio = null_cells / total_cells if total_cells > 0 else 0
        dup_ratio = duplicate_rows / len(df_flattened) if len(df_flattened) > 0 else 0
        quality_score = float(round(max(0.0, 1.0 - null_ratio - (dup_ratio * 0.5)), 2))

        columns_info = []
        for col in df_flattened.columns:
            series = df_flattened[col].dropna()
            info = {
                "name": col,
                "dtype": str(df_flattened[col].dtype),
                "null_count": int(df_flattened[col].isnull().sum()),
                "unique_count": int(df_flattened[col].nunique()),
                "sample_values": [str(v) for v in series.head(3).tolist()],
            }

            # Advanced stats for numeric columns
            if pd.api.types.is_numeric_dtype(df_flattened[col]) and len(series) >= 20:
                vals = series.values.astype(float)
                hurst = compute_hurst_exponent(vals)
                if hurst is not None:
                    info["hurst_exponent"] = float(round(hurst, 4))
                    info["trend_type"] = "trending" if hurst > 0.55 else ("mean-reverting" if hurst < 0.45 else "random-walk")
                
                cp = detect_change_points(vals)
                if cp: info["change_points_count"] = len(cp)
                
                season = compute_spectral_seasonality(vals)
                if season.get("period"):
                    info["dominant_period"] = season["period"]
                    info["seasonal_strength"] = float(season["strength"])

            columns_info.append(info)

        suggested = _generate_suggested_questions(columns_info)

        return {
            "schema_summary": {
                "collection_name": collection_name,
                "table_name": table_name,
                "total_documents": count,
                "columns": columns_info,
                "suggested_questions": suggested
            },
            "data_quality_score": quality_score,
            "table_name": table_name
        }
        
    except Exception as e:
        logger.error("json_discovery_failed", error_message=str(e), source_id=source_id)
        return {"error": f"Failed to ingest and profile JSON: {str(e)}"}


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
        questions = ["How many records are in this collection?", "What are the properties?"]
        
    return list(dict.fromkeys(questions))[:5]
