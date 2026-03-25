"""Analysis Use Case — orchestrates the dispatch of modular pipelines.

Implements Clean Architecture 'Use Case' layer.
Handles lazy loading of modular graphs to ensure team isolation.
"""

from __future__ import annotations

from typing import Any, Dict


def get_pipeline(source_type: str, checkpointer: Any = None):
    """Return the compiled LangGraph pipeline for PDF jobs."""
    from app.modules.pdf.workflow import build_pdf_graph
    return build_pdf_graph(checkpointer=checkpointer)
