"""PDF Indexing Agent — Vision-based ingestion using ColPali patches."""
import os
import uuid
import torch
import structlog
import json
from typing import Any, Dict, List, Optional
from PIL import Image
from pdf2image import convert_from_path, pdfinfo_from_path
from app.infrastructure.database.postgres import async_session_factory
from app.models.knowledge import Document, KnowledgeBase
from app.models.tenant import Tenant
from app.modules.pdf.flows.deep_vision.agents.pdf_agent import get_colpali
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = structlog.get_logger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HUMAN-AI SYNERGY: PURE CLASSIFICATION BY USER
#
#  With this approach, Gemini is completely removed from indexing.
#  Classification is instantly mapped from the user's Hint, providing 
#  100% deterministic, zero-cost, instantaneous metadata.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Maps user-selected hint → static classification metadata (no AI needed)
_HINT_TO_META: Dict[str, Dict[str, str]] = {
    # ── Finance & Accounting ──
    "invoice":          {"doc_type": "Invoice / Receipt",           "industry": "Finance"},
    "financial_report": {"doc_type": "Financial Report",            "industry": "Finance"},
    "tax_return":       {"doc_type": "Tax Return / Declaration",    "industry": "Finance"},
    "bank_statement":   {"doc_type": "Bank / Account Statement",    "industry": "Finance"},
    "purchase_order":   {"doc_type": "Purchase Order",              "industry": "Finance"},
    # ── Legal & Compliance ──
    "contract":         {"doc_type": "Legal Contract / Agreement",  "industry": "Legal"},
    "nda":              {"doc_type": "Non-Disclosure Agreement",    "industry": "Legal"},
    "policy":           {"doc_type": "Policy / Compliance Document","industry": "Legal"},
    "audit_report":     {"doc_type": "Audit / Compliance Report",   "industry": "Legal"},
    # ── Human Resources ──
    "hr_record":        {"doc_type": "HR / Personnel Record",       "industry": "Human Resources"},
    "resume":           {"doc_type": "Resume / CV",                 "industry": "Human Resources"},
    "perf_review":      {"doc_type": "Performance Review",          "industry": "Human Resources"},
    # ── Medical & Healthcare ──
    "medical_record":   {"doc_type": "Medical / Clinical Record",   "industry": "Medical"},
    "prescription":     {"doc_type": "Medical Prescription",        "industry": "Medical"},
    "lab_result":       {"doc_type": "Lab / Test Result",           "industry": "Medical"},
    # ── Tech & Engineering ──
    "tech_spec":        {"doc_type": "Technical Specification",     "industry": "Technology"},
    "api_doc":          {"doc_type": "API / Developer Documentation","industry": "Technology"},
    "arch_diagram":     {"doc_type": "Architecture Diagram / Doc",  "industry": "Technology"},
    # ── Logistics & Supply Chain ──
    "bill_of_lading":   {"doc_type": "Bill of Lading",              "industry": "Logistics"},
    "customs_decl":     {"doc_type": "Customs Declaration",         "industry": "Logistics"},
    "inventory":        {"doc_type": "Inventory / Stock Report",    "industry": "Logistics"},
    # ── Real Estate & Construction ──
    "lease_agreement":  {"doc_type": "Lease / Rental Agreement",    "industry": "Real Estate"},
    "property_deed":    {"doc_type": "Property Deed / Title",       "industry": "Real Estate"},
    "floor_plan":       {"doc_type": "Floor Plan / Blueprint",      "industry": "Construction"},
    # ── General Business ──
    "business_report":  {"doc_type": "Business / Strategy Report",  "industry": "Business"},
    "meeting_minutes":  {"doc_type": "Meeting Minutes",             "industry": "Business"},
    "marketing_mat":    {"doc_type": "Marketing Material / Deck",   "industry": "Marketing"},
    # ── Literature, Academic & Other ──
    "other_book":       {"doc_type": "Book / E-Book",               "industry": "Literature & Education"},
    "other_manual":     {"doc_type": "Instruction Manual",          "industry": "Literature & Education"},
    "other_research":   {"doc_type": "Research Paper",              "industry": "Academic & Research"},
    "other_article":    {"doc_type": "News Article / Blog",         "industry": "Academic & Research"},
    "other_misc":       {"doc_type": "General Document",            "industry": "Other / Custom"},
}

def _build_static_metadata(hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Instantly builds structured metadata based on the user's categorical hint.
    Bypasses AI completely for maximum speed and cost efficiency.
    
    Priority:
    1. Direct slug lookup in _HINT_TO_META (e.g., "invoice")
    2. Heritage parsing for "Industry: X | Type: Y" format
    3. Generic fallback
    """
    if not hint:
        return {
            "doc_type": "Unclassified Document",
            "industry": "Unknown",
            "source_hint": "none",
            "dna": {"summary": "Awaiting generic RAG analysis"},
            "specialized_fields": {}
        }
    
    # 1. Direct Slug Lookup (Fastest/Deterministic)
    clean_hint = hint.strip().lower()
    if clean_hint in _HINT_TO_META:
        static_meta = _HINT_TO_META[clean_hint]
        return {
            "doc_type": static_meta["doc_type"],
            "industry": static_meta["industry"],
            "source_hint": hint,
            "dna": {"summary": f"Strategic {static_meta['doc_type']} identified in {static_meta['industry']} domain."},
            "specialized_fields": {
                "classification_mode": "taxonomy_direct",
                "slug": clean_hint,
                "extracted_at": "2026-03-24T07:18:00Z"
            }
        }
    
    # 2. Heritage Parsing Fallback
    try:
        industry = "Unknown"
        doc_type = "Unclassified Document"
        
        if "|" in hint:
            parts = hint.split("|")
            for part in parts:
                if "Industry:" in part:
                    industry = part.replace("Industry:", "").strip()
                if "Type:" in part:
                    doc_type = part.replace("Type:", "").strip()
        else:
            industry = hint.strip()

        return {
            "doc_type": doc_type,
            "industry": industry,
            "source_hint": hint,
            "dna": {"summary": f"Strategic {doc_type} identified in {industry} domain (Parsed)."},
            "specialized_fields": {
                "classification_mode": "heritage_parsed",
                "extracted_at": "2026-03-24T07:18:00Z"
            }
        }
    except Exception as e:
        logger.error("hint_parsing_failed", hint=hint, error=str(e))
        return {
            "doc_type": "Parsing Error",
            "industry": "Error",
            "source_hint": hint,
            "dna": {"summary": "Failed to extract strategic signals from heritage hint."},
            "specialized_fields": {}
        }


async def indexing_agent(doc_id: str) -> Dict[str, Any]:
    """Indexes a PDF document into Qdrant using ColPali multi-vectors."""
    async with async_session_factory() as db:
        # Fetch document with its context hierarchy (KB -> Tenant)
        query = (
            select(Document)
            .options(
                selectinload(Document.kb).selectinload(KnowledgeBase.tenant)
            )
            .where(Document.id == uuid.UUID(doc_id))
        )
        res = await db.execute(query)
        doc = res.scalar_one_or_none()
        if not doc:
            return {"error": f"Document {doc_id} not found."}

        # Extract context
        context_hint = doc.context_hint
        kb_id = doc.kb_id
        file_path = doc.file_path

        doc.status = "processing"
        await db.commit()

        try:
            result = await _run_indexing_core(
                id_for_meta=str(doc.id),
                file_path=file_path,
                kb_id=kb_id,
                context_hint=context_hint,
                is_source=False
            )
            
            # Update Document with result
            doc.status = "done"
            doc.indexed_at = doc.updated_at
            doc.metadata_json = result.get("metadata")
            await db.commit()
            return {"status": "success", "pages_indexed": result.get("pages"), "doc_type": result.get("metadata", {}).get("doc_type")}
            
        except Exception as e:
            logger.error("indexing_failed", doc_id=doc_id, error=str(e))
            doc.status = "error"
            await db.commit()
            return {"error": str(e)}

async def indexing_agent_source(source_id: str) -> Dict[str, Any]:
    """Indexes a PDF DataSource into Qdrant using ColPali multi-vectors."""
    from app.models.data_source import DataSource
    async with async_session_factory() as db:
        query = select(DataSource).where(DataSource.id == uuid.UUID(source_id))
        res = await db.execute(query)
        source = res.scalar_one_or_none()
        if not source:
            return {"error": f"DataSource {source_id} not found."}

        context_hint = source.context_hint
        file_path = source.file_path
        
        # DataSource doesn't have a status field for indexing, but we can log it
        logger.info("source_indexing_started", source_id=source_id)

        try:
            result = await _run_indexing_core(
                id_for_meta=str(source.id),
                file_path=file_path,
                kb_id=None, # Direct uploads don't have kb_id
                context_hint=context_hint,
                is_source=True
            )
            
            # Optionally update source metadata
            source.schema_json = {
                **(source.schema_json or {}),
                "page_count": result.get("pages"),
                "indexed": True,
                "metadata": result.get("metadata")
            }
            source.indexing_status = "done"
            await db.commit()
            return {"status": "success", "pages_indexed": result.get("pages")}
            
        except Exception as e:
            logger.error("source_indexing_failed", source_id=source_id, error=str(e))
            async with async_session_factory() as db2:
                from sqlalchemy import update
                await db2.execute(
                    update(DataSource)
                    .where(DataSource.id == uuid.UUID(source_id))
                    .values(indexing_status="failed")
                )
                await db2.commit()
            return {"error": str(e)}

async def _run_indexing_core(id_for_meta: str, file_path: str, kb_id: Optional[uuid.UUID], context_hint: Optional[str], is_source: bool) -> Dict[str, Any]:
    """Core logic to index a PDF file into Qdrant."""
    if not file_path or not os.path.exists(file_path):
        raise ValueError(f"File not found at {file_path}")

    # Get page count to process page-by-page (Memory Efficiency)
    info = pdfinfo_from_path(file_path)
    total_pages = info["Pages"]
    
    model, processor = get_colpali()
    
    # Collection naming logic: kb_{kb_id} if exists, else ds_{source_id}
    if kb_id:
        collection_name = f"kb_{str(kb_id).replace('-', '')}"
    else:
        collection_name = f"ds_{str(id_for_meta).replace('-', '')}"
        
    qdrant = QdrantMultiVectorManager(collection_name=collection_name)
    await qdrant.ensure_collection()

    # Process in small chunks to avoid OOM
    CHUNK_SIZE = 1 
    for page_num in range(1, total_pages + 1, CHUNK_SIZE):
        last_page = min(page_num + CHUNK_SIZE - 1, total_pages)
        batch_images = convert_from_path(
            file_path, 
            dpi=150, 
            first_page=page_num, 
            last_page=last_page
        )
        
        if not batch_images:
            continue
        
        with torch.no_grad():
            processed_batch = processor.process_images(batch_images).to(model.device)
            image_embeddings = model.forward(**processed_batch)
            
            for i, image_emb in enumerate(image_embeddings):
                current_page = page_num + i
                page_vectors = image_emb.cpu().tolist()
                
                # Metadata for retrieval
                smart_metadata = {
                    "doc_id": id_for_meta if not is_source else None,
                    "source_id": id_for_meta if is_source else None,
                    "kb_id": str(kb_id) if kb_id else None,
                    "page_num": page_num,
                    "is_header_page": page_num == 1
                }

                import hashlib
                # Generate a deterministic UUID for the page point
                page_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{id_for_meta}_{page_num}")

                qdrant.upsert_page(
                    page_id=str(page_uuid),
                    colpali_vectors=page_vectors,
                    muvera_vector=[0.0] * 40960, # Placeholder
                    metadata=smart_metadata
                )
        
        del processed_batch
        del image_embeddings
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    doc_dna = _build_static_metadata(context_hint)
    return {"pages": len(images), "metadata": doc_dna}
