from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional
import structlog

logger = structlog.get_logger("app.sql.schema_mapper")

class SchemaMapper:
    """Manages business-friendly descriptions for technical database schemas."""

    def __init__(self, metadata_path: Optional[str] = None):
        self.storage_path = Path(metadata_path or "app/modules/sql/metadata/schema_descriptions.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.descriptions: Dict[str, Dict[str, str]] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load schema metadata from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("failed_to_load_schema_metadata", error=str(e))
        
        # Default starter metadata for Chinook (as examples)
        return {
            "tables": {
                "Invoice": "Contains specific sales transactions, including totals and dates.",
                "Track": "Individual songs or recordings available for purchase.",
                "Genre": "Music categories like Rock, Jazz, or Blues."
            },
            "columns": {
                "Invoice.Total": "The final amount charged to the customer after discounts.",
                "Track.Milliseconds": "The duration of the song in milliseconds (useful for calculating song length).",
                "Employee.ReportsTo": "The ID of the manager this employee answers to."
            }
        }

    def get_table_description(self, table_name: str) -> str:
        """Return the business description for a table."""
        return self.descriptions.get("tables", {}).get(table_name, "")

    def get_column_description(self, table_name: str, column_name: str) -> str:
        """Return the business description for a specific column."""
        key = f"{table_name}.{column_name}"
        return self.descriptions.get("columns", {}).get(key, "")

    def map_schema(self, schema_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Inject human-readable descriptions into the schema summary."""
        if not schema_summary.get("tables"):
            return schema_summary

        for table in schema_summary["tables"]:
            t_name = table["table"]
            table["description"] = self.get_table_description(t_name)
            
            for col in table.get("columns", []):
                c_name = col["name"]
                col["description"] = self.get_column_description(t_name, c_name)
        
        return schema_summary

# Singleton instance
schema_mapper = SchemaMapper()
