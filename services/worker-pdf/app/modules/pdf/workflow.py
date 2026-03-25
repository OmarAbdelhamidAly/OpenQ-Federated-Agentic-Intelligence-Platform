"""PDF Pipeline — 3-Way Architecture Router.

Segments requests based on `extraction_mode` to the respective isolated flow:
  - 'fast_text': Text only, high speed.
  - 'deep_vision': Full VLM multi-vector analysis, highest quality.
  - 'hybrid_ocr': Smart text + selective OCR, balanced layout.
"""
from typing import Any

def build_pdf_graph(checkpointer: Any = None, mode: str = "deep_vision") -> Any:
    """Route construction to the appropriate isolated PDF workflow."""
    
    if mode == "fast_text":
        from app.modules.pdf.flows.fast_text.workflow import build_fast_text_graph
        return build_fast_text_graph(checkpointer=checkpointer)
        
    elif mode == "hybrid_ocr":
        from app.modules.pdf.flows.hybrid_ocr.workflow import build_hybrid_ocr_graph
        return build_hybrid_ocr_graph(checkpointer=checkpointer)
        
    else:  # default to deep_vision
        from app.modules.pdf.flows.deep_vision.workflow import build_deep_vision_graph
        return build_deep_vision_graph(checkpointer=checkpointer)
