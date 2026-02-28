"""Tool: Run safe pandas query — method dispatch only, no exec/eval.

CSV Pipeline — pandas-based query execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field


class PandasQueryInput(BaseModel):
    """Input schema for run_pandas_query tool."""
    file_path: str = Field(..., description="Path to the CSV file")
    operation: Literal["groupby", "filter", "aggregate", "sort", "pivot"] = Field(
        ..., description="Pandas operation to perform"
    )
    group_by: Optional[List[str]] = Field(None, description="Column(s) to group by")
    agg_column: Optional[str] = Field(None, description="Column to aggregate")
    agg_function: Literal["sum", "mean", "count", "max", "min"] = Field(
        "sum", description="Aggregation function"
    )
    sort_by: Optional[str] = Field(None, description="Column to sort by")
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order")
    top_n: Optional[int] = Field(None, description="Top N results")
    filter_column: Optional[str] = Field(None, description="Column to filter on")
    filter_value: Optional[str] = Field(None, description="Value to filter for")


@tool("run_pandas_query", args_schema=PandasQueryInput)
def run_pandas_query(
    file_path: str,
    operation: str,
    group_by: Optional[List[str]] = None,
    agg_column: Optional[str] = None,
    agg_function: str = "sum",
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    top_n: Optional[int] = None,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a safe pandas query using method dispatch only.

    NEVER uses exec(), eval(), or string interpolation.
    NEVER writes to files, SQL, or external systems.
    """
    df = pd.read_csv(file_path)

    # Apply filter
    if filter_column and filter_value and filter_column in df.columns:
        df = df[df[filter_column].astype(str) == str(filter_value)]

    # Execute operation
    if operation == "groupby" and group_by and agg_column:
        valid_cols = [c for c in group_by if c in df.columns]
        if not valid_cols or agg_column not in df.columns:
            raise ToolException("Invalid column names for groupby operation.")
        agg_map = {"sum": "sum", "mean": "mean", "count": "count", "max": "max", "min": "min"}
        result = df.groupby(valid_cols)[agg_column].agg(agg_map[agg_function]).reset_index()

    elif operation == "aggregate" and agg_column:
        if agg_column not in df.columns:
            raise ToolException(f"Column '{agg_column}' not found.")
        agg_map = {"sum": "sum", "mean": "mean", "count": "count", "max": "max", "min": "min"}
        val = getattr(df[agg_column], agg_map[agg_function])()
        result = pd.DataFrame({agg_column: [val]})

    elif operation == "sort" and sort_by:
        if sort_by not in df.columns:
            raise ToolException(f"Column '{sort_by}' not found for sorting.")
        result = df.sort_values(by=sort_by, ascending=(sort_order == "asc"))

    elif operation == "pivot" and group_by and agg_column:
        valid_cols = [c for c in group_by if c in df.columns]
        if len(valid_cols) < 2:
            raise ToolException("Pivot requires at least 2 group_by columns.")
        result = df.pivot_table(
            index=valid_cols[0],
            columns=valid_cols[1],
            values=agg_column,
            aggfunc=agg_function,
        ).reset_index()

    else:
        result = df.head(100)

    # Apply top_n
    if top_n:
        result = result.head(top_n)

    return {
        "data": result.to_dict(orient="records"),
        "columns": list(result.columns),
        "row_count": len(result),
    }
