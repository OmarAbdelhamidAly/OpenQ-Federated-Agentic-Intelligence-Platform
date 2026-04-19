"""Strategic Nexus Indexer (PDF Flow 4).
Uses Hybrid OCR Foundation + Strategic Knowledge Mapping (Hierarchy & Entities).
"""
import os
import uuid
import structlog
import base64
import fitz
from typing import Dict, Any, List
from io import BytesIO

from app.infrastructure.llm import get_llm
from app.infrastructure.database.postgres import async_session_factory
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.modules.pdf.utils.taxonomy import get_document_taxonomy
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.models.data_source import DataSource
from sqlalchemy import select, update

logger = structlog.get_logger(__name__)

async def _process_image_ocr(page: fitz.Page, bbox: tuple, llm: Any) -> str:
    """Selective OCR for images/tables within a page."""
    try:
        rect = fitz.Rect(bbox)
        pix = page.get_pixmap(clip=rect, dpi=150)
        img_bytes = pix.tobytes("jpeg")
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "Extract all technical data and text from this image accurately. Focus on tables and technical names."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        )
        response = await llm.ainvoke([msg])
        return response.content
    except Exception as e:
        logger.warning("hybrid_ocr_image_failed", error=str(e))
        return "[Image Content]"

async def strategic_nexus_indexer(source_id: str) -> Dict[str, Any]:
    """Fourth Standalone Indexing Flow: High-Fidelity Graph Ingestion."""
    logger.info("strategic_nexus_indexing_started", source_id=source_id)
    
    # 1. Resolve File
    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source: return {"error": "Source not found"}
        file_path = source.file_path
        context_hint = source.context_hint

    if not os.path.exists(file_path): return {"error": "File not found"}

    # 2. Hybrid Extraction Layer (Native + OCR)
    llm = get_llm(temperature=0) # Using centralized LLM factory
    full_content = []
    chunk_data = []

    if file_path.lower().endswith(".txt"):
         with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text_content = f.read()
            if text_content.strip():
                chunk_data.append({
                    "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_strat_0")),
                    "text": text_content.strip(),
                    "page": 1,
                    "chunk_index": 0
                })
                full_content.append(text_content.strip())
         logger.info("strategic_text_file_extraction_done", file=file_path)
    else:
        doc = fitz.open(file_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict").get("blocks", [])
            page_text = ""
            
            for b in blocks:
                if b.get("type") == 0: # Text
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            page_text += span.get("text", "") + " "
                    page_text += "\n"
                elif b.get("type") == 1: # Image/Table
                    ocr_result = await _process_image_ocr(page, b.get("bbox"), llm)
                    page_text += f"\n[IMAGE_DATA]: {ocr_result}\n"
            
            chunk_data.append({
                "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_strat_{page_num}")),
                "text": page_text.strip(),
                "page": page_num + 1,
                "chunk_index": page_num
            })
            full_content.append(page_text)
        doc.close()

    # 3. Strategic Mapping Step (LLM Structure Discovery)
    # We send the unified text to LLM to understand Sections & Entities
    # To avoid context window issues with giant docs, we send the first 10,000 words
    truncated_text = "\n".join(full_content)[:50000] 
    
    mapping_prompt = f"""
    You are a Strategic Knowledge Architect. Analyze the following document content (extracted via Hybrid OCR).
    Identify the logical structure (Sections) and key domain entities (Concepts, Technical Terms).
    
    CONTEXT: {context_hint or 'General Business Doc'}
    
    EXTRACTED TEXT:
    {truncated_text}
    
    Respond with a strictly formatted JSON object:
    {{
       "sections": [
          {{"title": "Section Title", "level": 1, "summary": "Brief summary", "page_range": [1, 2]}}
       ],
       "entities": [
          {{"name": "Term Name", "type": "Technical/Business/System", "description": "Brief definition", "at_pages": [1]}}
       ]
    }}
    """
    
    try:
        from langchain_core.output_parsers import JsonOutputParser
        parser = JsonOutputParser()
        res = await llm.ainvoke(mapping_prompt)
        # Use simple string parsing if LLM output isn't clean
        import json
        mapping = res.content
        if "```json" in mapping:
            mapping = mapping.split("```json")[1].split("```")[0].strip()
        knowledge_map = json.loads(mapping)
    except Exception as e:
        logger.warning("strategic_mapping_failed", error=str(e))
        knowledge_map = {"sections": [], "entities": []}

    # 4. Neo4j Knowledge Graph Sync
    neo4j = Neo4jAdapter()
    taxonomy = get_document_taxonomy(context_hint)
    
    # Sync basic chunks first
    await neo4j.batch_upsert_document_structure(source_id, source_id, chunk_data, taxonomy)
    
    # Sync Hierarchy
    sections_to_sync = []
    for i, s in enumerate(knowledge_map.get("sections", [])):
        # Map page range to chunk IDs
        p_start, p_end = s.get("page_range", [1, 1])
        c_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_strat_{p-1}")) for p in range(p_start, p_end + 1)]
        sections_to_sync.append({
            "id": f"sec_{i}_{source_id}",
            "title": s["title"],
            "summary": s.get("summary", ""),
            "level": s.get("level", 1),
            "chunk_ids": c_ids
        })
    await neo4j.batch_upsert_strategic_hierarchy(source_id, source_id, sections_to_sync)
    
    # Sync Entities
    entities_to_sync = []
    for ent in knowledge_map.get("entities", []):
        p_list = ent.get("at_pages", [1])
        c_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_strat_{p-1}")) for p in p_list]
        entities_to_sync.append({
            "name": ent["name"],
            "type": ent.get("type", "Concept"),
            "description": ent.get("description", ""),
            "chunk_ids": c_ids
        })
    await neo4j.batch_upsert_entities(source_id, entities_to_sync)

    # 5. Finalize DataSource Status
    async with async_session_factory() as db:
        await db.execute(
            update(DataSource).where(DataSource.id == uuid.UUID(source_id))
            .values(indexing_status="done", 
                    schema_json={**source.schema_json, "indexed": True, "mode": "strategic_nexus", "progress": 100})
        )
        await db.commit()

    return {"status": "success", "sections": len(sections_to_sync), "entities": len(entities_to_sync)}
