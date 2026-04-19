"""Fast PDF Indexing Agent — Text-based, Cloud Embeddings (Gemini).

Pipeline:
  PDF → PyMuPDF text extraction → RecursiveCharacterTextSplitter (300 tokens)
       → Google Gemini Embeddings (768-dim) → Qdrant MultiVector upsert

Unified with the Deep Vision flow for a consistent vector database structure.
"""
from __future__ import annotations

import os
import uuid
import structlog
from typing import Any, Dict, List, Optional

from app.modules.pdf.flows.deep_vision.agents.indexing_agent import _get_embedding_model
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager

logger = structlog.get_logger(__name__)


def _extract_text_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extract text from PDF (page-by-page) or .txt (whole file). Returns list of page dicts."""
    pages = []
    
    if not file_path.lower().endswith(".pdf"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
            if full_text.strip():
                # Treat whole txt as one virtual page for metadata consistency
                pages.append({"page_num": 1, "text": full_text.strip()})
        logger.info("text_file_extraction_done", file=file_path)
    else:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text and text.strip():
                pages.append({"page_num": page_num + 1, "text": text.strip()})
        doc.close()
        logger.info("pdf_extraction_done", file=file_path, pages_with_text=len(pages))
        
    return pages


def _split_into_chunks(pages: List[Dict[str, Any]], chunk_size: int = 300, overlap: int = 50) -> List[Dict[str, Any]]:
    """Split page text into overlapping chunks using a simple word-based splitter.
    Implements Parent-Child chunking: keeps full page context attached to every small chunk.
    """
    chunks = []
    for page in pages:
        words = page["text"].split()
        step = chunk_size - overlap
        for start in range(0, len(words), step):
            chunk_words = words[start: start + chunk_size]
            if len(chunk_words) < 20:  # Skip tiny fragments
                continue
            chunks.append({
                "page_num": page["page_num"],
                "text": " ".join(chunk_words), # Child: High precision for vector similarity
                "parent_text": page["text"],   # Parent: Deep context for synthesis 
                "chunk_index": len(chunks),
            })
    logger.info("chunking_done_parent_child", total_chunks=len(chunks))
    return chunks


# ── Public API ─────────────────────────────────────────────────────────────────

async def fast_indexing_agent(source_id: str) -> Dict[str, Any]:
    """Index a PDF DataSource using the cloud-based fast text pipeline."""
    from app.models.data_source import DataSource
    from app.infrastructure.database.postgres import async_session_factory
    from sqlalchemy import select, update

    logger.info("unified_fast_indexing_started", source_id=source_id)

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            return {"error": f"DataSource {source_id} not found"}

        file_path = source.file_path
        initial_schema = source.schema_json or {}

    try:
        # 1. Text Extraction
        pages = _extract_text_from_pdf(file_path)
        if not pages:
            raise ValueError("No text extracted from PDF.")

        # 2. Chunking
        chunks = _split_into_chunks(pages, chunk_size=300, overlap=50)

        # 3. Gemini Embedding & Qdrant Sync
        embed_model = _get_embedding_model()
        collection_name = f"ds_{source_id.replace('-', '')}" # Unifying with vision naming
        qdrant = QdrantMultiVectorManager(collection_name=collection_name)
        await qdrant.ensure_collection(text_vector_size=768)

        for i, chunk in enumerate(chunks):
            # Embed chunk
            text_vector = embed_model.embed_query(chunk["text"])
            
            # Upsert as a specific text chunk point
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_text_{i}"))
            qdrant.upsert_page(
                page_id=point_id,
                text_vector=text_vector,
                metadata={
                    "source_id": source_id,
                    "page_num": chunk["page_num"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "parent_text": chunk["parent_text"],
                    "is_text_chunk": True,
                    "chunk_strategy": "parent_child"
                }
            )
            
            # Progress reporting
            if i % 10 == 0:
                progress = min(20 + int((i / len(chunks)) * 70), 95)
                async with async_session_factory() as db:
                    await db.execute(
                        update(DataSource)
                        .where(DataSource.id == uuid.UUID(source_id))
                        .values(schema_json={**initial_schema, "progress": progress, "current_step": f"Indexing Text: Chunk {i}/{len(chunks)}"})
                    )
                    await db.commit()

        # 4. Neo4j Knowledge Graph Sync (Universal Synthesis Layer)
        try:
            from app.infrastructure.neo4j_adapter import Neo4jAdapter
            from app.modules.pdf.utils.taxonomy import get_document_taxonomy
            neo4j = Neo4jAdapter()
            
            # Prepare chunks for Neo4j structure
            neo4j_chunks = []
            for i, chunk in enumerate(chunks):
                neo4j_chunks.append({
                    "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}_text_{i}")),
                    "text": chunk["text"],
                    "page": chunk["page_num"],
                    "chunk_index": chunk["chunk_index"]
                })
            
            # Get Taxonomy
            taxonomy = get_document_taxonomy(source.context_hint)
            
            await neo4j.batch_upsert_document_structure(
                source_id=source_id,
                document_id=source_id,
                chunks=neo4j_chunks,
                taxonomy=taxonomy
            )
            logger.info("neo4j_sync_done", source_id=source_id, chunks=len(neo4j_chunks))
        except Exception as neo_err:
            logger.warning("neo4j_sync_failed_secondary", error=str(neo_err))

        # 5. Final Updates
        async with async_session_factory() as db:
            await db.execute(
                update(DataSource)
                .where(DataSource.id == uuid.UUID(source_id))
                .values(
                    indexing_status="done",
                    schema_json={
                        **initial_schema,
                        "page_count": len(pages),
                        "chunk_count": len(chunks),
                        "indexed": True,
                        "indexing_mode": "fast_text",
                        "progress": 100,
                        "current_step": "Fast Text indexing complete (Cloud Gemini)."
                    },
                )
            )
            await db.commit()

        return {"status": "success", "mode": "fast_text", "chunks": len(chunks)}

    except Exception as e:
        logger.error("fast_indexing_failed", source_id=source_id, error=str(e))
        async with async_session_factory() as db:
            await db.execute(
                update(DataSource)
                .where(DataSource.id == uuid.UUID(source_id))
                .values(indexing_status="failed", last_error=str(e))
            )
            await db.commit()
        return {"error": str(e), "status": "failed"}
