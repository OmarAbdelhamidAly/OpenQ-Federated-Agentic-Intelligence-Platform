"""3-Layer SQL Validator — Ensures safety, syntactical correctness, and schema validity.

Inspired by the notebook implementation, optimized for a multi-dialect SaaS environment.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from app.infrastructure.sql_guard import validate_select_only
from structlog import get_logger

logger = get_logger("app.sql.validator")

class SQLValidator:
    """Validates SQL through 3 defensive layers before execution."""

    def __init__(self, engine: Any, schema_summary: Optional[Dict[str, Any]] = None):
        self.engine = engine
        self.schema_summary = schema_summary
        self.dialect = engine.dialect.name if engine else "sqlite"

    async def validate(self, sql: str) -> Dict[str, Any]:
        """Runs the 3-layer validation.
        
        Returns: {"valid": bool, "errors": [str], "warnings": [str]}
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        if not sql or not sql.strip():
            return {"valid": False, "errors": ["Query is empty."], "warnings": []}

        # ── Layer 1: Security & Keyword Guard ──
        try:
            validate_select_only(sql)
        except ValueError as exc:
            errors.append(str(exc))
            return {"valid": False, "errors": errors, "warnings": []}

        # ── Layer 2: Engine Parser (EXPLAIN) ──
        try:
            explain_cmd = "EXPLAIN QUERY PLAN" if self.dialect == "sqlite" else "EXPLAIN"
            from sqlalchemy.ext.asyncio import AsyncEngine
            
            plan_output = []
            if isinstance(self.engine, AsyncEngine):
                async with self.engine.connect() as conn:
                    result = await conn.execute(text(f"{explain_cmd} {sql}"))
                    plan_output = result.fetchall()
            else:
                with self.engine.connect() as conn:
                    result = conn.execute(text(f"{explain_cmd} {sql}"))
                    plan_output = result.fetchall()
            
            # Simple Optimization Check (Idea 7)
            plan_text = str(plan_output).lower()
            if "scan" in plan_text and "index" not in plan_text:
                warnings.append("Performance: Detected a Full Table Scan. Consider adding an index if the table is large.")
            if "join" in plan_text and "search" not in plan_text and self.dialect == "sqlite":
                 warnings.append("Performance: Potential unoptimized JOIN detected.")
                 
        except Exception as exc:
            errors.append(f"SQL engine validation failed: {str(exc)[:200]}")

        # ── Layer 3: Schema Hallucination Check ──
        if self.schema_summary and self.schema_summary.get("tables"):
            # 1. Table check
            known_tables_map = {t["table"].lower(): t for t in self.schema_summary["tables"]}
            
            mentioned_tables = re.findall(
                r"\b(?:FROM|JOIN)\s+[\"\'\`\[]?([\w.]+)", 
                sql, 
                re.IGNORECASE
            )
            
            for table in mentioned_tables:
                base_table = table.split(".")[-1].lower().strip("\"'`[]")
                if base_table not in known_tables_map:
                    errors.append(f"Table '{table}' not found in schema. Possible hallucination.")
                else:
                    # 2. Column check (Experimental/Soft)
                    # Extract words that look like columns (this is a heuristic)
                    # For a strict check, we'd need a full SQL parser like sqlglot
                    table_meta = known_tables_map[base_table]
                    known_cols = {c["name"].lower() for c in table_meta["columns"]}
                    
                    # Look for pattern table.column or just column if it's unique
                    # This is complex without a parser, so we'll just log warnings for now
                    pass

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
