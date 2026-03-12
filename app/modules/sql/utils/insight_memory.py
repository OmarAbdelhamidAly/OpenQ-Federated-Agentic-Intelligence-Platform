from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("app.sql.insight_memory")

class InsightMemory:
    """Manages long-term memory of successful SQL analyses (Idea 16)."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or ".cache/insight_memory.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        """Load history from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("failed_to_load_insight_memory", error=str(e))
        return []

    def save_analysis(self, question: str, sql: str, insight: str, metrics: Any = None):
        """Save a successful analysis to memory."""
        self.memory.append({
            "question": question,
            "sql": sql,
            "insight": insight,
            "metrics": metrics
        })
        # Keep only the last 50 insights
        if len(self.memory) > 50:
            self.memory = self.memory[-50:]
            
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_insight_memory", error=str(e))

    def get_related_insights(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Retrieve past insights related to the query using keyword matching."""
        scored = []
        query_terms = set(query.lower().split())
        
        for item in self.memory:
            item_terms = set(item["question"].lower().split())
            score = len(query_terms.intersection(item_terms))
            scored.append((score, item))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:limit] if score > 0]

insight_memory = InsightMemory()
