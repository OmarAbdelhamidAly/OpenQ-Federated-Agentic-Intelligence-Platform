from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("app.sql.golden_sql")

class GoldenSQLManager:
    """Manages a library of known-correct SQL examples for few-shot prompting."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or ".cache/golden_sql.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.examples: List[Dict[str, str]] = self._load_examples()

    def _load_examples(self) -> List[Dict[str, str]]:
        """Load examples from disk, or return defaults if empty."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("failed_to_load_golden_sql", error=str(e))
        
        # Default "Golden" examples for the Chinook dataset (standard for tests/demo)
        return [
            {
                "question": "Who are the top 5 customers by total spending?",
                "sql": "SELECT c.FirstName, c.LastName, SUM(i.Total) as TotalSpent FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId ORDER BY TotalSpent DESC LIMIT 5;"
            },
            {
                "question": "List all tracks in the 'Rock' genre.",
                "sql": "SELECT t.Name FROM Track t JOIN Genre g ON t.GenreId = g.GenreId WHERE g.Name = 'Rock' LIMIT 100;"
            },
            {
                "question": "Which artist has the most albums?",
                "sql": "SELECT ar.Name, COUNT(al.AlbumId) as AlbumCount FROM Artist ar JOIN Album al ON ar.ArtistId = al.ArtistId GROUP BY ar.ArtistId ORDER BY AlbumCount DESC LIMIT 1;"
            },
            {
                "question": "What is the total revenue for 2023?",
                "sql": "SELECT SUM(Total) FROM Invoice WHERE InvoiceDate >= '2023-01-01' AND InvoiceDate <= '2023-12-31';"
            }
        ]

    def get_similar_examples(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
        """Retrieve examples most relevant to the user query.
        
        Currently uses simple keyword matching. In a production env, 
        this would use the Qdrant retrieval logic from retrieval.py.
        """
        # Keyword-based heuristic for now
        scored_examples = []
        query_terms = set(query.lower().split())
        
        for ex in self.examples:
            ex_terms = set(ex["question"].lower().split())
            score = len(query_terms.intersection(ex_terms))
            scored_examples.append((score, ex))
            
        # Sort by score and take top limit
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        return [ex for score, ex in scored_examples[:limit]]

    def add_example(self, question: str, sql: str):
        """Add a new golden example to the library."""
        self.examples.append({"question": question, "sql": sql})
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.examples, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_golden_sql", error=str(e))

# Singleton instance
golden_sql_manager = GoldenSQLManager()
