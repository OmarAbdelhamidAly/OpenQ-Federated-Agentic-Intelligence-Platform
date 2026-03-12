from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text

from app.infrastructure.sql_guard import validate_select_only
from app.modules.shared.tools.load_data_source import ensure_async_connection_string


class SQLQueryInput(BaseModel):
    """Input schema for run_sql_query tool."""
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    query: str = Field(..., description="SELECT query to execute")
    params: Optional[Dict[str, Any]] = Field(
        None, description="Named parameters for the query"
    )
    limit: int = Field(1000, description="Max rows to return", ge=1, le=10000)


# ── Shared Connection Pooling & Caching ─────────────────────────────────────────

_ENGINES: Dict[str, AsyncEngine] = {}
_RESULT_CACHE: Dict[tuple, Dict[str, Any]] = {}


def get_async_engine(connection_string: str) -> AsyncEngine:
    """Return a cached SQLAlchemy async engine or create a new one."""
    async_conn_str = ensure_async_connection_string(connection_string)
    if async_conn_str not in _ENGINES:
        # SQLite does not support pool_size or max_overflow
        if async_conn_str.startswith("sqlite"):
            _ENGINES[async_conn_str] = create_async_engine(async_conn_str)
        else:
            _ENGINES[async_conn_str] = create_async_engine(
                async_conn_str,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_pre_ping=True
            )
    return _ENGINES[async_conn_str]


async def _run_sql_query_internal(
    connection_string: str,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Execute a SELECT-only SQL query asynchronously with pooling and caching."""
    # 1. Validation & Cleaning
    clean_query = query.strip().rstrip(";")
    try:
        validate_select_only(clean_query)
    except ValueError as exc:
        raise ToolException(str(exc))

    if not re.search(r"\bLIMIT\b", clean_query, re.IGNORECASE):
        clean_query += f" LIMIT {limit}"

    # 2. Result Caching Check
    cache_key = (
        connection_string,
        clean_query,
        tuple(sorted((params or {}).items()))
    )
    if cache_key in _RESULT_CACHE:
        return _RESULT_CACHE[cache_key]

    # 3. Execution with Shared Async Pool
    engine = get_async_engine(connection_string)
    try:
        async with engine.connect() as conn:
            # Idea 4: Stream results for memory efficiency
            result = await conn.stream(text(clean_query), params or {})
            
            data: List[Dict[str, Any]] = []
            columns = list(result.keys())
            
            count = 0
            async for row in result:
                if count >= limit:
                    break
                
                # Zip columns and row values
                data.append({col: val for col, val in zip(columns, row)})
                count += 1

            output = {
                "data": data,
                "columns": columns,
                "row_count": len(data),
                "truncated": count >= limit, # Flag for the agent (Idea 4)
                "cached": False
            }
            
            # Simple cache management (limit to 100 items)
            if len(_RESULT_CACHE) > 100:
                _RESULT_CACHE.clear()
            _RESULT_CACHE[cache_key] = output
            
            return output
            
    except Exception as e:
        raise ToolException(f"Async SQL execution error: {e}")


@tool("run_sql_query", args_schema=SQLQueryInput)
async def run_sql_query(
    connection_string: str,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Execute a SELECT-only SQL query asynchronously with pooling and caching."""
    return await _run_sql_query_internal(connection_string, query, params, limit)
