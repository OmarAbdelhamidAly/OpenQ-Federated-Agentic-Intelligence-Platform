"""Tool: Compute top-N ranking with delta vs prior period.

CSV Pipeline — works with CSV files via pandas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class RankingInput(BaseModel):
    """Input schema for compute_ranking tool."""
    file_path: str = Field(..., description="Path to the CSV file")
    rank_column: str = Field(..., description="Column to rank by (numeric)")
    label_column: str = Field(..., description="Column with labels/names")
    top_n: int = Field(10, description="Number of top results", ge=1, le=100)
    sort_order: Literal["desc", "asc"] = Field("desc", description="Sort order")
    date_column: Optional[str] = Field(
        None, description="Date column for period-over-period comparison"
    )


@tool("compute_ranking", args_schema=RankingInput)
def compute_ranking(
    file_path: str,
    rank_column: str,
    label_column: str,
    top_n: int = 10,
    sort_order: str = "desc",
    date_column: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute top-N ranking with optional delta vs prior period."""
    df = pd.read_csv(file_path)

    if rank_column not in df.columns or label_column not in df.columns:
        return {"error": f"Column '{rank_column}' or '{label_column}' not found."}

    ascending = sort_order == "asc"

    if date_column and date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        df = df.dropna(subset=[date_column])

        # Split into current and prior period (by median date)
        median_date = df[date_column].median()
        current = df[df[date_column] >= median_date]
        prior = df[df[date_column] < median_date]

        current_rank = (
            current.groupby(label_column)[rank_column]
            .sum()
            .sort_values(ascending=ascending)
            .head(top_n)
        )
        prior_rank = prior.groupby(label_column)[rank_column].sum()

        rankings: List[Dict[str, Any]] = []
        for rank, (label, value) in enumerate(current_rank.items(), 1):
            prior_val = prior_rank.get(label, 0)
            delta = float(value - prior_val)
            delta_pct = round(delta / prior_val * 100, 2) if prior_val != 0 else 0
            rankings.append({
                "rank": rank,
                "label": str(label),
                "value": round(float(value), 2),
                "prior_value": round(float(prior_val), 2),
                "delta": round(delta, 2),
                "delta_pct": delta_pct,
            })

        return {"rankings": rankings, "has_period_comparison": True}
    else:
        # Simple ranking without period comparison
        ranked = (
            df.groupby(label_column)[rank_column]
            .sum()
            .sort_values(ascending=ascending)
            .head(top_n)
        )

        rankings = [
            {"rank": i, "label": str(label), "value": round(float(val), 2)}
            for i, (label, val) in enumerate(ranked.items(), 1)
        ]

        return {"rankings": rankings, "has_period_comparison": False}
