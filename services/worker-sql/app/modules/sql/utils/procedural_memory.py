"""Procedural Memory for SQL Worker.
Stores 'How-To' instructions and Golden Queries so the agent doesn't need to reason from scratch.
"""

class ProceduralMemory:
    GOLDEN_QUERIES = {
        "trend": "Use DATE_TRUNC('month', date_col) and GROUP BY 1 ORDER BY 1. Always ensure chronological sorting.",
        "comparison": "Use GROUP BY category and order by the metric DESC to highlight the largest segments.",
        "anomaly": "Look for spikes mapping OUTSIDE 2 standard deviations or use simple LAG() window functions."
    }

    def get_procedural_knowledge(self, intent: str) -> str:
        """Fetch instinctive SQL templates based on the user's intent."""
        return self.GOLDEN_QUERIES.get(intent.lower(), "Write clean, standard SQL with appropriate joins and limits.")

procedural_memory = ProceduralMemory()
