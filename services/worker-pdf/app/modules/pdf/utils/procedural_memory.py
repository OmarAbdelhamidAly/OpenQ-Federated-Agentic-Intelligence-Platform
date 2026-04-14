"""Procedural Memory for PDF Worker.
Stores extraction instincts so the agent doesn't need to reason through complex layout tasks.
"""

class ProceduralMemory:
    ROUTINES = {
        "comparison": "Use Hybrid OCR. Extract tables from both documents, align their schemas mathematically, and compare row-by-row.",
        "summary": "Use Fast Text. Locate 'Executive Summary' and 'Conclusion' headings. Ignore appendices.",
        "financial": "Use Deep Vision (ColPali). Focus heavily on visual charts, balance sheets, and bar graphs."
    }

    def get_procedural_knowledge(self, intent: str) -> str:
        """Fetch instinctive processing instructions based on the document intent."""
        return self.ROUTINES.get(intent.lower(), "Extract text chunks chronologically and synthesize carefully.")

procedural_memory = ProceduralMemory()
