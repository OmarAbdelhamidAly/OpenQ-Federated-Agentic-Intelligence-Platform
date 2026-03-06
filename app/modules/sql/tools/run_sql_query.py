"""Tool: Run SELECT-only SQL query via SQLAlchemy parameterized queries.

SQL Pipeline — executes queries against relational databases.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.infrastructure.sql_guard import validate_select_only


class SQLQueryInput(BaseModel):
    """Input schema for run_sql_query tool."""
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    query: str = Field(..., description="SELECT query to execute")
    params: Optional[Dict[str, Any]] = Field(
        None, description="Named parameters for the query"
    )
    limit: int = Field(1000, description="Max rows to return", ge=1, le=10000)


# ── Shared Connection Pooling & Caching ─────────────────────────────────────────

_ENGINES: Dict[str, Any] = {}
_RESULT_CACHE: Dict[tuple, Dict[str, Any]] = {}

def get_engine(connection_string: str):
    """Return a cached SQLAlchemy engine or create a new one."""
    if connection_string not in _ENGINES:
        _ENGINES[connection_string] = create_engine(
            connection_string,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True
        )
    return _ENGINES[connection_string]


@tool("run_sql_query", args_schema=SQLQueryInput)
def run_sql_query(
    connection_string: str,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Execute a SELECT-only SQL query via SQLAlchemy with pooling and caching."""
    # 1. Validation & Cleaning
    clean_query = query.strip().rstrip(";")
    try:
        validate_select_only(clean_query)
    except ValueError as exc:
        raise ToolException(str(exc))

    if not re.search(r"\bLIMIT\b", clean_query, re.IGNORECASE):
        clean_query += f" LIMIT {limit}"

    # 2. Result Caching Check
    # Key = (conn_str, query, sorted_params)
    cache_key = (
        connection_string,
        clean_query,
        tuple(sorted((params or {}).items()))
    )
    if cache_key in _RESULT_CACHE:
        return _RESULT_CACHE[cache_key]

    # 3. Execution with Shared Pool
    engine = get_engine(connection_string)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(clean_query), params or {})
            rows = result.fetchall()
            columns = list(result.keys())

            data: List[Dict[str, Any]] = [
                {col: val for col, val in zip(columns, row)}
                for row in rows
            ]

            output = {
                "data": data,
                "columns": columns,
                "row_count": len(data),
                "cached": False
            }
            
            # Simple cache management (limit to 100 items)
            if len(_RESULT_CACHE) > 100:
                _RESULT_CACHE.clear()
            _RESULT_CACHE[cache_key] = output
            
            return output
            
    except Exception as e:
        raise ToolException(f"SQL execution error: {e}")
