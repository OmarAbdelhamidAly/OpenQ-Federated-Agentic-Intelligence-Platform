import fitz
import base64
import os
import uuid
import structlog
from typing import Dict, Any

from app.infrastructure.llm import get_llm
from app.infrastructure.config import settings
from app.infrastructure.database.postgres import async_session_factory
from app.models.data_source import DataSource
from app.models.knowledge import Document
from app.domain.analysis.entities import AnalysisState
from sqlalchemy import select
from langchain_core.messages import HumanMessage

logger = structlog.get_logger(__name__)

async def _process_image_block(page: fitz.Page, bbox: tuple, llm: Any) -> str:
    """Crop the specific image/table block and send it to LLM for OCR."""
    try:
        # Crop the bounding box directly from the high-res page
        rect = fitz.Rect(bbox)
        pix = page.get_pixmap(clip=rect, dpi=150)
        img_bytes = pix.tobytes("jpeg")
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "Extract all text, tables, and data from this image accurately. Preserve layout and Arabic diacritics (tashkeel) if present."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        )
        response = await llm.ainvoke([msg])
        return response.content + "\n\n"
    except Exception as e:
        logger.error("hybrid_ocr_image_failed", error=str(e))
        return "[Image OCR Failed]\n\n"

async def hybrid_ocr_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Smart Hybrid Pipeline: Segments text from images to optimize inference.
    Native text is extracted instantly via PyMuPDF.
    Image blocks are selectively sent to a VLM (Gemini via centralized LLM factory).
    """
    source_id = state.get("source_id")
    kb_id = state.get("kb_id")
    
    logger.info("hybrid_ocr_agent_started", source_id=source_id, kb_id=kb_id)
    
    pdf_path = None
    async with async_session_factory() as db:
        if source_id:
            res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
            obj = res.scalar_one_or_none()
            if obj: pdf_path = obj.file_path
        elif kb_id:
            res = await db.execute(select(Document).where(Document.kb_id == uuid.UUID(kb_id)))
            obj = res.scalars().first()
            if obj: pdf_path = obj.file_path

    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning("pdf_not_found", path=pdf_path)
        return {"visual_context": [{"page": 1, "text": f"PDF not found at {pdf_path}. Cannot perform Hybrid OCR."}]}
        
    doc = fitz.open(pdf_path)
    visual_context = []
    
    # Use centralized LLM factory for OCR (Ideally a Vision-capable model)
    llm = get_llm(temperature=0)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict").get("blocks", [])
        
        page_text = f"## Page {page_num + 1}\n"
        
        for b in blocks:
            # Block Type 0 = Text
            if b.get("type") == 0:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        page_text += span.get("text", "") + " "
                page_text += "\n"
                
            # Block Type 1 = Image/Figure
            elif b.get("type") == 1:
                bbox = b.get("bbox")
                ocr_text = await _process_image_block(page, bbox, llm)
                page_text += f"\n[Extracted via OCR]:\n{ocr_text}\n"
                
        visual_context.append({
            "page": page_num + 1,
            "text": page_text.strip()
        })
        
    logger.info("hybrid_ocr_agent_completed", total_pages=len(doc))
    return {"visual_context": visual_context}
