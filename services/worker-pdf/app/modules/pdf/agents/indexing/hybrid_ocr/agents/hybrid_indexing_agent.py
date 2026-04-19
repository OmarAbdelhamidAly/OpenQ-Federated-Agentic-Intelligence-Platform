"""Hybrid Indexing Agent.
Persistent indexing that combines native text with selective OCR.
"""
import os
import uuid
import structlog
import fitz
from typing import Dict, Any, List

from app.modules.pdf.agents.indexing.hybrid_ocr.agents.hybrid_ocr_agent import _process_image_block
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.modules.pdf.utils.taxonomy import get_document_taxonomy
from app.infrastructure.llm import get_llm
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.database.postgres import async_session_factory
from app.models.data_source import DataSource
from sqlalchemy import select, update

logger = structlog.get_logger(__name__)

async def hybrid_indexing_agent(source_id: str) -> Dict[str, Any]:
    """Index a PDF Source using the Hybrid OCR pipeline."""
    logger.info("hybrid_indexing_started", source_id=source_id)

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source: return {"error": "Source not found"}
        file_path = source.file_path
        context_hint = source.context_hint

    if not os.path.exists(file_path): return {"error": "File not found"}

    doc = fitz.open(file_path)
    llm = get_llm(temperature=0)
    
    chunk_data = []
    
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
                ocr_result = await _process_image_block(page, b.get("bbox"), llm)
                page_text += f"\n[OCR Content]: {ocr_result}\n"
        
        chunk_data.append({
            "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_hybrid_{page_num}")),
            "text": page_text.strip(),
            "page": page_num + 1,
            "chunk_index": page_num
        })

    # 1. Qdrant Sync
    from app.modules.pdf.agents.indexing.deep_vision.agents.indexing_agent import _get_embedding_model
    embed_model = _get_embedding_model()
    collection_name = f"ds_{source_id.replace('-', '')}"
    qdrant = QdrantMultiVectorManager(collection_name=collection_name)
    await qdrant.ensure_collection(text_vector_size=768)

    for chunk in chunk_data:
        text_vector = embed_model.embed_query(chunk["text"])
        qdrant.upsert_page(
            page_id=chunk["chunk_id"],
            text_vector=text_vector,
            metadata={
                "source_id": source_id,
                "page_num": chunk["page"],
                "text": chunk["text"],
                "indexing_mode": "hybrid"
            }
        )

    # 2. Neo4j Sync
    neo4j = Neo4jAdapter()
    taxonomy = get_document_taxonomy(context_hint)
    await neo4j.batch_upsert_document_structure(source_id, source_id, chunk_data, taxonomy)

    # 3. Finalize
    async with async_session_factory() as db:
        await db.execute(
            update(DataSource).where(DataSource.id == uuid.UUID(source_id))
            .values(indexing_status="done", 
                    schema_json={**source.schema_json, "indexed": True, "mode": "hybrid", "progress": 100})
        )
        await db.commit()

    return {"status": "success", "mode": "hybrid", "chunks": len(chunk_data)}
