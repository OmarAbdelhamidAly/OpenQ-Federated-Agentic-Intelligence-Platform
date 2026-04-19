"""
Hybrid OCR Synthesis Agent — Powered by Unstructured.io (strategy=ocr_only)

Upgraded from manual PyMuPDF block detection to Unstructured's intelligent
element classification. Unstructured automatically handles:
  - Native text extraction from text blocks
  - OCR for image blocks (via Tesseract/PaddleOCR)
  - Table structure detection and preservation
  - Element boundary classification

The Vision LLM is still invoked for Image/Figure elements that need
high-quality semantic description beyond what raw OCR provides.
"""
import os
import base64
import uuid
import structlog
from io import BytesIO
from typing import Dict, Any, List

from app.infrastructure.llm import get_llm
from app.infrastructure.config import settings
from app.infrastructure.database.postgres import async_session_factory
from app.models.data_source import DataSource
from app.models.knowledge import Document
from app.domain.analysis.entities import AnalysisState
from sqlalchemy import select
from langchain_core.messages import HumanMessage

from app.modules.pdf.utils.unstructured_partitioner import (
    partition_document,
    recommend_strategy,
    ElementType,
    DocumentChunk,
)

logger = structlog.get_logger(__name__)


async def hybrid_ocr_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Hybrid OCR Synthesis Agent using Unstructured (strategy='ocr_only').

    Replaces the manual PyMuPDF blocks loop with Unstructured's element
    classification engine. Native text is used as-is; Image elements are
    sent to Vision LLM for high-quality semantic description.

    Output format is backward-compatible with the verifier_agent.
    """
    source_id = state.get("source_id")
    kb_id = state.get("kb_id")

    logger.info("hybrid_ocr_agent_started", source_id=source_id, kb_id=kb_id)

    # ── 1. Resolve file path ───────────────────────────────────────────────────
    file_path = None
    async with async_session_factory() as db:
        if source_id:
            res = await db.execute(
                select(DataSource).where(DataSource.id == uuid.UUID(source_id))
            )
            obj = res.scalar_one_or_none()
            if obj:
                file_path = obj.file_path
        elif kb_id:
            res = await db.execute(
                select(Document).where(Document.kb_id == uuid.UUID(kb_id))
            )
            obj = res.scalars().first()
            if obj:
                file_path = obj.file_path

    if not file_path or not os.path.exists(file_path):
        logger.warning("hybrid_ocr_file_not_found", path=file_path)
        return {
            "visual_context": [{
                "page": 1,
                "text": f"Document not found at {file_path}. Cannot perform OCR analysis."
            }]
        }

    # ── 2. Partition with OCR strategy ────────────────────────────────────────
    strategy = recommend_strategy(file_path, indexing_mode="hybrid")
    logger.info("hybrid_ocr_partitioning", file=os.path.basename(file_path),
                strategy=strategy)

    try:
        partition_result = partition_document(file_path, strategy_override=strategy)
    except Exception as e:
        logger.error("hybrid_ocr_partition_failed", error=str(e))
        return {
            "visual_context": [{
                "page": 1,
                "text": f"OCR partitioning failed: {str(e)}"
            }]
        }

    text_chunks = [c for c in partition_result.chunks
                   if c.element_type != ElementType.IMAGE]
    image_chunks = [c for c in partition_result.chunks
                    if c.element_type == ElementType.IMAGE]

    logger.info("hybrid_ocr_partition_done",
                text_chunks=len(text_chunks),
                image_chunks=len(image_chunks),
                total_pages=partition_result.page_count)

    # ── 3. Build page-grouped context from text elements ──────────────────────
    # Group text chunks by page number — backward-compatible with verifier_agent
    page_context: Dict[int, str] = {}
    for chunk in text_chunks:
        page_num = chunk.page_num
        if page_num not in page_context:
            page_context[page_num] = f"## Page {page_num}\n"
        # Prefix Table/Code elements with type indicator for clear synthesis
        if chunk.element_type == ElementType.TABLE:
            page_context[page_num] += f"\n[TABLE]\n{chunk.text}\n[/TABLE]\n"
        elif chunk.element_type == ElementType.CODE:
            page_context[page_num] += f"\n```\n{chunk.text}\n```\n"
        else:
            page_context[page_num] += chunk.text + " "

    # ── 4. Process Image elements with Vision LLM ─────────────────────────────
    if image_chunks:
        llm = get_llm(temperature=0)
        logger.info("hybrid_ocr_vision_phase", image_count=len(image_chunks))

        for img_chunk in image_chunks:
            page_num = img_chunk.page_num
            ocr_text = await _describe_image_page(file_path, page_num, llm)

            if page_num not in page_context:
                page_context[page_num] = f"## Page {page_num}\n"
            page_context[page_num] += f"\n[Visual Content — Vision OCR]\n{ocr_text}\n"

    # ── 5. Build final visual_context list (backward-compatible) ──────────────
    visual_context = [
        {"page": page_num, "text": page_text.strip()}
        for page_num, page_text in sorted(page_context.items())
    ]

    logger.info("hybrid_ocr_agent_completed",
                total_pages=len(visual_context),
                has_tables=partition_result.has_tables,
                has_images=partition_result.has_images)

    return {"visual_context": visual_context}


async def _describe_image_page(file_path: str, page_num: int, llm) -> str:
    """
    Sends a specific page's image to the Vision LLM for high-quality OCR.
    Used only for pages that contain Image elements detected by Unstructured.
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            from pdf2image import convert_from_path
            images = convert_from_path(
                file_path, dpi=150,
                first_page=page_num, last_page=page_num
            )
            if not images:
                return "[Image extraction failed — no page rendered]"
            page_image = images[0]
            page_image.thumbnail((1120, 1120))

            from io import BytesIO
            buffered = BytesIO()
            page_image.save(buffered, format="JPEG", quality=80)
            img_bytes = buffered.getvalue()

        elif ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
        else:
            return f"[Visual description not available for file type: {ext}]"

        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        msg = HumanMessage(content=[
            {
                "type": "text",
                "text": (
                    "Extract all text, tables, and data from this image accurately. "
                    "Use STRICT MARKDOWN FORMATTING. "
                    "For tables: use standard Markdown table syntax (| Col | Col |). "
                    "Preserve layout hierarchy with headers (#) and lists (-)."
                )
            },
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
        ])
        response = await llm.ainvoke([msg])
        return response.content + "\n\n"

    except Exception as e:
        logger.error("hybrid_ocr_vision_failed", page=page_num, error=str(e))
        return f"[Vision OCR failed for page {page_num}: {str(e)}]\n\n"
