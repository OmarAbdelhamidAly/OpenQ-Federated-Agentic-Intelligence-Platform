"""Tool: Compute time-series trend — slope + anomaly detection.

CSV Pipeline — works with CSV files via pandas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class TrendInput(BaseModel):
    """Input schema for compute_trend tool."""
    file_path: str = Field(..., description="Path to the CSV file")
    date_column: str = Field(..., description="Column with date/time values")
    value_column: str = Field(..., description="Column with numeric values to analyze")
    group_by: Optional[str] = Field(None, description="Optional column to group trends by")


@tool("compute_trend", args_schema=TrendInput)
def compute_trend(
    file_path: str,
    date_column: str,
    value_column: str,
    group_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute time-series trend: slope, direction, anomalies via IQR method."""
    df = pd.read_csv(file_path)

    if date_column not in df.columns or value_column not in df.columns:
        return {"error": f"Columns '{date_column}' or '{value_column}' not found."}

    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df = df.dropna(subset=[date_column, value_column])
    df = df.sort_values(date_column)

    def _compute_single_trend(data: pd.DataFrame) -> Dict[str, Any]:
        values = data[value_column].values.astype(float)
        x = np.arange(len(values), dtype=float)

        if len(values) < 2:
            return {"slope": 0, "direction": "flat", "anomalies": []}

        # Linear regression for slope
        slope = float(np.polyfit(x, values, 1)[0])

        # Direction
        if abs(slope) < 0.01 * np.mean(values):
            direction = "flat"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        # Anomaly detection via IQR
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        anomaly_mask = (values < lower) | (values > upper)
        anomaly_indices = np.where(anomaly_mask)[0].tolist()
        anomalies = [
            {
                "index": int(i),
                "date": str(data[date_column].iloc[i]),
                "value": float(values[i]),
            }
            for i in anomaly_indices
        ]

        # Percentage change
        pct_change = float((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0

        return {
            "slope": round(slope, 4),
            "direction": direction,
            "pct_change": round(pct_change, 2),
            "start_value": float(values[0]),
            "end_value": float(values[-1]),
            "min_value": float(np.min(values)),
            "max_value": float(np.max(values)),
            "data_points": len(values),
            "anomalies": anomalies,
        }

    if group_by and group_by in df.columns:
        results = {}
        for name, group in df.groupby(group_by):
            results[str(name)] = _compute_single_trend(group)
        return {"grouped_trends": results}
    else:
        return _compute_single_trend(df)
