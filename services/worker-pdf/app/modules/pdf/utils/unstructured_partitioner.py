"""
Universal Document Partitioner — Powered by Unstructured.io

Replaces the combination of:
  - PyMuPDF raw text extraction (fast_text flow)
  - Manual pdfinfo page-by-page rendering (deep_vision flow)
  - Manual block detection loop (hybrid_ocr flow)

Provides a single, intelligent entry point for ANY document format.
Supported formats:
  .pdf .docx .doc .odt .pptx .ppt .xlsx .csv .tsv
  .eml .msg .rtf .epub .html .xml .png .jpg .jpeg .txt .md
"""
from __future__ import annotations

import os
import uuid
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = structlog.get_logger(__name__)


# ── Element Type Classification ───────────────────────────────────────────────

class ElementType(str, Enum):
    TITLE = "Title"
    NARRATIVE_TEXT = "NarrativeText"
    TABLE = "Table"
    CODE = "CodeSnippet"
    IMAGE = "Image"
    LIST_ITEM = "ListItem"
    HEADER = "Header"
    FOOTER = "Footer"
    FORMULA = "Formula"
    UNKNOWN = "Unknown"


@dataclass
class DocumentChunk:
    """A single semantically-aware chunk ready for embedding."""
    chunk_id: str
    text: str                        # Child text — used for vector search
    parent_text: str                 # Parent context — used for synthesis
    element_type: ElementType
    page_num: int
    chunk_index: int
    atomic: bool = False             # If True, this chunk must never be split further
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartitionResult:
    """Output of the universal partitioner."""
    chunks: List[DocumentChunk]
    doc_strategy: str                # "fast" | "hi_res" | "ocr_only" | "auto"
    detected_file_type: str
    total_elements: int
    has_tables: bool
    has_images: bool
    has_code: bool
    page_count: int


# ── Strategy Selection Map ────────────────────────────────────────────────────

# Maps file extension → Unstructured partitioning strategy
_STRATEGY_MAP: Dict[str, str] = {
    # Pure native text — traditional NLP is perfect
    ".docx": "fast", ".doc": "fast", ".odt": "fast",
    ".txt": "fast",  ".md": "fast",  ".rtf": "fast",
    ".html": "fast", ".htm": "fast", ".xml": "fast",
    ".epub": "fast", ".eml": "fast", ".msg": "fast",
    # Rich layout / spreadsheets — auto selects the right parser
    ".pptx": "auto", ".ppt": "auto",
    ".xlsx": "auto", ".csv": "auto", ".tsv": "auto",
    # PDF — decided dynamically based on content characteristics
    ".pdf": "auto",
    # Pure image files — OCR is the only path
    ".png": "ocr_only", ".jpg": "ocr_only", ".jpeg": "ocr_only",
    ".tiff": "ocr_only", ".bmp": "ocr_only", ".webp": "ocr_only",
}

# Atomic element types — these must NEVER be split mid-content
_ATOMIC_TYPES = {ElementType.TABLE, ElementType.CODE, ElementType.TITLE,
                 ElementType.HEADER, ElementType.FOOTER, ElementType.FORMULA}


# ── Core Partition Function ───────────────────────────────────────────────────

def partition_document(
    file_path: str,
    strategy_override: Optional[str] = None,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> PartitionResult:
    """
    Partitions any supported document into semantically-aware chunks.

    Args:
        file_path: Absolute path to the document.
        strategy_override: Force a specific strategy ("fast", "hi_res", "ocr_only", "auto").
                           If None, auto-detected from file extension.
        chunk_size: Max words per child chunk for NarrativeText.
        chunk_overlap: Overlap words between consecutive NarrativeText chunks.

    Returns:
        PartitionResult with classified, chunked elements ready for embedding.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    strategy = strategy_override or _STRATEGY_MAP.get(ext, "auto")

    logger.info("partitioning_document",
                file=os.path.basename(file_path),
                extension=ext,
                strategy=strategy)

    # ── Call Unstructured ──────────────────────────────────────────────────────
    try:
        from unstructured.partition.auto import partition
        raw_elements = partition(
            filename=file_path,
            strategy=strategy,
            # Include page numbers in metadata for all elements
            include_page_breaks=True,
        )
    except ImportError:
        logger.error("unstructured_not_installed",
                     hint="pip install 'unstructured[pdf,docx,pptx,xlsx,md,html,epub,eml]'")
        raise
    except Exception as e:
        logger.error("partition_failed", file=file_path, strategy=strategy, error=str(e))
        # Graceful fallback: attempt with "fast" strategy
        if strategy != "fast":
            logger.warning("partition_fallback_to_fast", file=file_path)
            return partition_document(file_path, strategy_override="fast",
                                      chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        raise

    logger.info("partition_complete",
                file=os.path.basename(file_path),
                raw_element_count=len(raw_elements))

    # ── Classify & Chunk Elements ─────────────────────────────────────────────
    chunks = _build_chunks(raw_elements, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # ── Collect Stats ─────────────────────────────────────────────────────────
    type_set = {c.element_type for c in chunks}
    page_nums = {c.page_num for c in chunks if c.page_num > 0}

    return PartitionResult(
        chunks=chunks,
        doc_strategy=strategy,
        detected_file_type=ext.lstrip("."),
        total_elements=len(raw_elements),
        has_tables=ElementType.TABLE in type_set,
        has_images=ElementType.IMAGE in type_set,
        has_code=ElementType.CODE in type_set,
        page_count=max(page_nums) if page_nums else 1,
    )


# ── Element Classification ────────────────────────────────────────────────────

def _classify_element(element) -> ElementType:
    """Maps an Unstructured element to our internal ElementType enum."""
    cls_name = type(element).__name__

    _TYPE_MAP = {
        "Title": ElementType.TITLE,
        "NarrativeText": ElementType.NARRATIVE_TEXT,
        "Table": ElementType.TABLE,
        "CodeSnippet": ElementType.CODE,
        "Image": ElementType.IMAGE,
        "FigureCaption": ElementType.IMAGE,
        "Figure": ElementType.IMAGE,
        "ListItem": ElementType.LIST_ITEM,
        "Header": ElementType.HEADER,
        "Footer": ElementType.FOOTER,
        "Formula": ElementType.FORMULA,
        "Text": ElementType.NARRATIVE_TEXT,
        "UncategorizedText": ElementType.NARRATIVE_TEXT,
        "Address": ElementType.NARRATIVE_TEXT,
        "EmailAddress": ElementType.NARRATIVE_TEXT,
        "PageBreak": ElementType.UNKNOWN,
    }
    return _TYPE_MAP.get(cls_name, ElementType.UNKNOWN)


def _get_page_num(element) -> int:
    """Safely extracts page number from Unstructured element metadata."""
    try:
        return element.metadata.page_number or 1
    except AttributeError:
        return 1


# ── Element-Aware Chunker ─────────────────────────────────────────────────────

def _build_chunks(raw_elements: list, chunk_size: int, chunk_overlap: int) -> List[DocumentChunk]:
    """
    Converts raw Unstructured elements into semantically-aware DocumentChunks.

    Rules:
    - Tables   → single atomic chunk (NEVER split — destroys structure)
    - Code     → single atomic chunk (NEVER split — breaks logic)
    - Titles   → single atomic chunk (anchors context)
    - Images   → single chunk with [IMAGE] placeholder text
    - Text     → Parent-Child sliding window split
    - ListItem → grouped with parent page context
    """
    chunks: List[DocumentChunk] = []
    chunk_index = 0

    for element in raw_elements:
        el_type = _classify_element(element)
        page_num = _get_page_num(element)
        text = (element.text or "").strip()

        if not text or len(text) < 5 or el_type == ElementType.UNKNOWN:
            continue

        if el_type in _ATOMIC_TYPES:
            # ── Atomic elements: never split ──────────────────────────────────
            chunk_id = str(uuid.uuid4())
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=text,
                parent_text=text,
                element_type=el_type,
                page_num=page_num,
                chunk_index=chunk_index,
                atomic=True,
                metadata={"unstructured_class": type(element).__name__},
            ))
            chunk_index += 1

        elif el_type == ElementType.IMAGE:
            # ── Image placeholder — will be routed to Vision LLM later ────────
            chunks.append(DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                text="[IMAGE ELEMENT — requires visual analysis]",
                parent_text="[IMAGE ELEMENT — requires visual analysis]",
                element_type=ElementType.IMAGE,
                page_num=page_num,
                chunk_index=chunk_index,
                atomic=True,
                metadata={
                    "is_image": True,
                    "unstructured_class": type(element).__name__,
                },
            ))
            chunk_index += 1

        else:
            # ── Text / ListItem: Parent-Child sliding window ───────────────────
            parent_text = text
            words = text.split()

            if len(words) <= chunk_size:
                # Short enough: keep as single chunk
                chunks.append(DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=text,
                    parent_text=parent_text,
                    element_type=el_type,
                    page_num=page_num,
                    chunk_index=chunk_index,
                    atomic=False,
                ))
                chunk_index += 1
            else:
                # Sliding window split
                step = max(chunk_size - chunk_overlap, 1)
                for start in range(0, len(words), step):
                    child_words = words[start: start + chunk_size]
                    if len(child_words) < 15:  # skip tiny trailing fragments
                        continue
                    chunks.append(DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        text=" ".join(child_words),
                        parent_text=parent_text,  # Full element as parent context
                        element_type=el_type,
                        page_num=page_num,
                        chunk_index=chunk_index,
                        atomic=False,
                    ))
                    chunk_index += 1

    logger.info("chunking_complete",
                total_chunks=len(chunks),
                atomic_chunks=sum(1 for c in chunks if c.atomic),
                image_chunks=sum(1 for c in chunks if c.element_type == ElementType.IMAGE))

    return chunks


# ── Utility: Get Image-Only Chunks  ──────────────────────────────────────────

def get_image_chunks(result: PartitionResult) -> List[DocumentChunk]:
    """Returns only the Image-type chunks for Vision LLM processing."""
    return [c for c in result.chunks if c.element_type == ElementType.IMAGE]


def get_text_chunks(result: PartitionResult) -> List[DocumentChunk]:
    """Returns all non-Image chunks ready for FastEmbed embedding."""
    return [c for c in result.chunks if c.element_type != ElementType.IMAGE]


# ── Strategy Recommendation (for worker.py routing) ──────────────────────────

def recommend_strategy(file_path: str, indexing_mode: Optional[str] = None) -> str:
    """
    Recommends the Unstructured strategy for a given file based on extension
    and requested indexing mode.

    Returns: "fast" | "hi_res" | "ocr_only" | "auto"
    """
    ext = os.path.splitext(file_path)[1].lower()

    # Explicit override by indexing mode
    if indexing_mode == "deep_vision":
        return "hi_res"
    if indexing_mode == "hybrid":
        return "ocr_only"
    if indexing_mode == "fast_text":
        return "fast"

    # Default from extension
    return _STRATEGY_MAP.get(ext, "auto")
