from __future__ import annotations
import re
from typing import Any, Dict, List, Set

class SemanticSchemaSelector:
    """Filters large database schemas to include only relevant tables for a given query."""

    @staticmethod
    def select_tables(schema_summary: Dict[str, Any], query: str, top_k: int = 10) -> Dict[str, Any]:
        """Return a filtered version of the schema summary.
        
        Uses a heuristic-based semantic match:
        1. Exact/Partial match on table names.
        2. Exact/Partial match on column names.
        3. Including tables linked via Foreign Keys to already selected tables.
        """
        if not schema_summary.get("tables") or len(schema_summary["tables"]) <= top_k:
            return schema_summary

        query_terms = set(re.findall(r"\w+", query.lower()))
        selected_table_names: Set[str] = set()

        # Phase 1: Direct matches (Heuristic)
        for t in schema_summary["tables"]:
            t_name = t["table"].lower()
            # Table name match
            if any(term in t_name for term in query_terms):
                selected_table_names.add(t["table"])
                continue
            
            # Column name match
            for c in t["columns"]:
                c_name = c["name"].lower()
                if any(term == c_name for term in query_terms):
                    selected_table_names.add(t["table"])
                    break
        
        # Phase 2: Join Path preservation (1-hop FK expansion)
        # If we pick 'Invoice', we should probably pick 'Customer' too if there is a relationship.
        expansion_set = set()
        for fk in schema_summary.get("foreign_keys", []):
            if fk["from_table"] in selected_table_names:
                expansion_set.add(fk["to_table"])
            if fk["to_table"] in selected_table_names:
                expansion_set.add(fk["from_table"])
        
        selected_table_names.update(expansion_set)

        # Reconstruct filtered summary
        filtered_tables = [t for t in schema_summary["tables"] if t["table"] in selected_table_names]
        
        # If we still have too many or too few, we could limit here, but for now we trust the expansion
        if not filtered_tables:
            return schema_summary # Fallback to full if nothing found
            
        return {
            **schema_summary,
            "tables": filtered_tables,
            "filtered": True,
            "original_table_count": len(schema_summary["tables"])
        }

schema_selector = SemanticSchemaSelector()
