"""Tool: Run SELECT-only SQL query via SQLAlchemy parameterized queries.

SQL Pipeline — executes queries against relational databases.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text


# Forbidden SQL operations — NEVER allow these
_FORBIDDEN_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE|MERGE)\b",
    re.IGNORECASE,
)


class SQLQueryInput(BaseModel):
    """Input schema for run_sql_query tool."""
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    query: str = Field(..., description="SELECT query to execute")
    params: Optional[Dict[str, Any]] = Field(
        None, description="Named parameters for the query"
    )
    limit: int = Field(1000, description="Max rows to return", ge=1, le=10000)


@tool("run_sql_query", args_schema=SQLQueryInput)
def run_sql_query(
    connection_string: str,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Execute a SELECT-only SQL query via SQLAlchemy.

    CRITICAL SAFETY:
    - ONLY SELECT queries are allowed.
    - INSERT, UPDATE, DELETE, DROP, ALTER, etc. are IMMEDIATELY rejected.
    - All queries use parameterized execution. No string interpolation. Ever.
    """
    # Strip and validate
    clean_query = query.strip().rstrip(";")

    # MUST start with SELECT or WITH (for CTEs)
    if not re.match(r"^\s*(SELECT|WITH)\b", clean_query, re.IGNORECASE):
        raise ToolException(
            "BLOCKED: Only SELECT queries are allowed. "
            "This platform is strictly read-only."
        )

    # Check for forbidden operations anywhere in the query
    if _FORBIDDEN_PATTERNS.search(clean_query):
        raise ToolException(
            "BLOCKED: Query contains forbidden operations. "
            "Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, DROP, ALTER."
        )

    # Apply LIMIT if not present
    if not re.search(r"\bLIMIT\b", clean_query, re.IGNORECASE):
        clean_query += f" LIMIT {limit}"

    # Execute with parameterized query
    engine = create_engine(connection_string)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(clean_query), params or {})
            rows = result.fetchall()
            columns = list(result.keys())

            data: List[Dict[str, Any]] = [
                {col: val for col, val in zip(columns, row)}
                for row in rows
            ]

            return {
                "data": data,
                "columns": columns,
                "row_count": len(data),
            }
    except Exception as e:
        raise ToolException(f"SQL execution error: {e}")
    finally:
        engine.dispose()
