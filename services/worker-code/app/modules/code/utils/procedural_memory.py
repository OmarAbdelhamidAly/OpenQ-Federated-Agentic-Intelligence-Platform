"""Procedural Memory for Code Worker.
Stores 'How-To' Cypher templates so the agent doesn't need to reason from scratch.
"""

class ProceduralMemory:
    GOLDEN_CYPHER = {
        "dependency": "MATCH (c:Class)-[:CALLS]->(target:Class) RETURN c, target. Use shortestPath() if asking for deep traces.",
        "implementation": "MATCH (c:Class)-[:IMPLEMENTS]->(i:Interface) RETURN c",
        "database": "MATCH (c:Class)-[:REPRESENTS_DATA]->(t:Table) RETURN c.name, t.name"
    }

    def get_procedural_knowledge(self, intent: str) -> str:
        """Fetch instinctive Cypher templates based on the user's intent."""
        return self.GOLDEN_CYPHER.get(intent.lower(), "Use MATCH and WHERE n.source_id = $source_id. Never guess property names.")

procedural_memory = ProceduralMemory()
