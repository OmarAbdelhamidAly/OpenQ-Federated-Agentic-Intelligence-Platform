from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, inspect, text


class SQLSchemaInput(BaseModel):
    """Input schema for sql_schema_discovery tool."""
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    schema_name: Optional[str] = Field(None, description="Schema name")
    sample_rows: int = Field(3, description="Sample rows count")
    force_refresh: bool = Field(False, description="Bypass cache")


def _quoted(name: str) -> str:
    return f'"{name}"'


def _fetch_table_metadata(
    engine: Any,
    inspector: Any,
    table_name: str,
    effective_schema: Optional[str],
    sample_rows: int
) -> Dict[str, Any]:
    """Independent helper for table introspection."""
    with engine.connect() as conn:
        columns = inspector.get_columns(table_name, schema=effective_schema)
        pk_constraint = inspector.get_pk_constraint(table_name, schema=effective_schema)
        pk_cols = set(pk_constraint.get("constrained_columns", []))
        
        fks = inspector.get_foreign_keys(table_name, schema=effective_schema)
        t_foreign_keys = []
        for fk in fks:
            for constrained, referred in zip(fk["constrained_columns"], fk["referred_columns"]):
                t_foreign_keys.append({
                    "from_table": table_name,
                    "from_col": constrained,
                    "to_table": fk["referred_table"],
                    "to_col": referred
                })

        row_count = 0
        try:
            qualified = f'"{effective_schema}"."{table_name}"' if effective_schema else f'"{table_name}"'
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar() or 0
        except Exception:
            pass

        col_infos = []
        for col in columns:
            col_name = col["name"]
            col_info = {
                "name": col_name,
                "dtype": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col_name in pk_cols,
                "sample_values": [],
                "low_cardinality_values": []
            }

            qualified = f'"{effective_schema}"."{table_name}"' if effective_schema else f'"{table_name}"'
            
            col_type_str = str(col["type"]).lower()
            if row_count > 0 and any(t in col_type_str for t in ["string", "varchar", "text", "char", "int"]):
                try:
                    stmt = text(f"SELECT COUNT(DISTINCT {_quoted(col_name)}) FROM {qualified}")
                    distinct_count = conn.execute(stmt).scalar() or 0
                    if 0 < distinct_count <= 25:
                        val_stmt = text(f"SELECT DISTINCT {_quoted(col_name)} FROM {qualified} WHERE {_quoted(col_name)} IS NOT NULL LIMIT 25")
                        values = conn.execute(val_stmt).fetchall()
                        col_info["low_cardinality_values"] = [str(v[0]) for v in values]
                except Exception:
                    pass

            if sample_rows > 0:
                try:
                    sample_stmt = text(f"SELECT {_quoted(col_name)} FROM {qualified} WHERE {_quoted(col_name)} IS NOT NULL LIMIT :n")
                    rows = conn.execute(sample_stmt, {"n": sample_rows}).fetchall()
                    col_info["sample_values"] = [str(r[0]) for r in rows]
                except Exception:
                    pass
            col_infos.append(col_info)

        return {
            "table": {
                "table": table_name,
                "schema": effective_schema,
                "columns": col_infos,
                "column_count": len(col_infos),
                "row_count": row_count,
            },
            "fks": t_foreign_keys
        }


def _sql_schema_discovery(
    connection_string: str,
    schema_name: Optional[str] = None,
    sample_rows: int = 3,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Internal implementation of schema discovery."""
    cache_dir = Path(".cache/schemas")
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_hash = hashlib.md5(f"{connection_string}|{schema_name}|{sample_rows}".encode()).hexdigest()
    cache_file = cache_dir / f"{db_hash}.json"
    
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                data["cached"] = True
                return data
        except Exception: pass

    engine = create_engine(connection_string)
    try:
        inspector = inspect(engine)
        dialect = engine.dialect.name
        effective_schema = schema_name
        if effective_schema is None and dialect == "postgresql":
            effective_schema = "public"

        tables = inspector.get_table_names(schema=effective_schema)
        schema_tables = []
        foreign_keys = []
        total_columns = 0
        
        for table_name in tables:
            res = _fetch_table_metadata(engine, inspector, table_name, effective_schema, sample_rows)
            schema_tables.append(res["table"])
            foreign_keys.extend(res["fks"])
            total_columns += len(res["table"]["columns"])

        output = {
            "dialect": dialect,
            "schema": effective_schema,
            "table_count": len(tables),
            "total_columns": total_columns,
            "tables": schema_tables,
            "foreign_keys": foreign_keys,
            "all_column_names": [f"{t['table']}.{c['name']}" for t in schema_tables for c in t["columns"]],
            "cached": False
        }
        try:
            with open(cache_file, "w") as f: json.dump(output, f)
        except Exception: pass
        return output
    except Exception as exc:
        raise ToolException(f"Schema discovery failed: {exc}")
    finally:
        engine.dispose()


@tool("sql_schema_discovery", args_schema=SQLSchemaInput)
def sql_schema_discovery(
    connection_string: str,
    schema_name: Optional[str] = None,
    sample_rows: int = 3,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Introspect a SQL database and return a structured schema summary.

    Discovers all tables, columns, data types, nullable flags, and sample values.
    Includes caching (Idea 1) and cardinality detection (Idea 12).
    """
    return _sql_schema_discovery(connection_string, schema_name, sample_rows, force_refresh)
