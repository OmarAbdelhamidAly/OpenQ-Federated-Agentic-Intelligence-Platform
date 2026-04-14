"""Procedural Memory for Nexus — Strategic Blueprint repository."""

class ProceduralMemory:
    """Stores 'Golden Blueprints' for strategic multi-pillar reasoning."""

    BLUEPRINTS = {
        "root_cause": """
        BLUEPRINT: Root Cause Analysis (Cross-Pillar)
        1. Identify the symptom in the Data Pillar (SQL/CSV).
        2. Look for corresponding Code entities (Class/Function) in the Graph.
        3. Trace dependencies/calls in the Code Pillar to find the logic error.
        4. Cross-reference with Documentation (PDF) for intended business logic.
        """,
        "audit": """
        BLUEPRINT: Structural Compliance Audit
        1. Compare Database schema (SQL) with Code entities (Graph).
        2. Check for missing indexes or orphaned tables.
        3. Verify against Design Docs (PDF) for architectural alignment.
        """,
        "discovery": """
        BLUEPRINT: Knowledge Graph Exploration
        1. Identify key entities in the query.
        2. Search Neo4j for N-degree relationships.
        3. Use the bridge nodes (e.g., MENTIONS, CALLS) to jump between PDF, Code, and SQL.
        """
    }

    def get_procedural_knowledge(self, intent: str) -> str:
        """Return the blueprint for a given strategic intent."""
        return self.BLUEPRINTS.get(intent, self.BLUEPRINTS["discovery"])

procedural_memory = ProceduralMemory()
