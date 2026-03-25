import fitz
import base64
import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import structlog
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

# Initialize the LLM (Ensure GOOGLE_API_KEY is configured in the environment)
try:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
except Exception as e:
    logger.warning("gemini_init_failed", error=str(e))
    llm = None

async def _process_image_block(page: fitz.Page, bbox: tuple) -> str:
    """Crop the specific image/table block and send it to Gemini Flash for OCR."""
    if not llm:
        return "[LLM Not Configured for OCR]"
        
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
    Image blocks are selectively sent to a VLM (Gemini Flash).
    """
    logger.info("hybrid_ocr_agent_started", source_id=state["source_id"])
    
    pdf_path = f"/tmp/tenants/{state['tenant_id']}/{state['source_id']}.pdf"
    
    if not os.path.exists(pdf_path):
        logger.warning("pdf_not_found_locally", path=pdf_path)
        return {"visual_context": [{"page": 1, "text": "PDF not found locally for Hybrid OCR."}]}
        
    doc = fitz.open(pdf_path)
    visual_context = []
    
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
                ocr_text = await _process_image_block(page, bbox)
                page_text += f"\n[Extracted from Image/Figure via Gemini Flash OCR]:\n{ocr_text}\n"
                
        visual_context.append({
            "page": page_num + 1,
            "text": page_text.strip()
        })
        
    logger.info("hybrid_ocr_agent_completed", total_pages=len(doc))
    
    return {
        "visual_context": visual_context
    }
