"""
Fast Document Indexing Agent — Universal Document Support via Unstructured.io

Pipeline:
  Any Document → Unstructured Partitioner (strategy="fast" / "auto")
               → Element-Aware Chunker (Tables & Code stay atomic)
               → FastEmbed (768d, nomic-ai/nomic-embed-text-v1.5)
               → Qdrant MultiVector upsert + Neo4j Knowledge Graph sync

Supported file types:
  .pdf .docx .doc .odt .pptx .ppt .xlsx .csv .tsv
  .eml .msg .rtf .epub .html .xml .txt .md
"""
from __future__ import annotations

import os
import uuid
import structlog
from typing import Any, Dict, List, Optional

from app.modules.pdf.agents.indexing.deep_vision.agents.indexing_agent import _get_embedding_model
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.modules.pdf.utils.unstructured_partitioner import (
    partition_document,
    get_text_chunks,
    recommend_strategy,
    ElementType,
)

logger = structlog.get_logger(__name__)

# ── Public API ─────────────────────────────────────────────────────────────────

async def fast_indexing_agent(source_id: str) -> Dict[str, Any]:
    """
    Index any supported document using element-aware fast text pipeline.
    
    This replaces the previous PyMuPDF + Word-based splitter with Unstructured's
    intelligent element classification, preserving Tables, Code, and Titles as
    atomic units that are never split mid-structure.
    """
    from app.models.data_source import DataSource
    from app.infrastructure.database.postgres import async_session_factory
    from sqlalchemy import select, update

    logger.info("universal_fast_indexing_started", source_id=source_id)

    # ── Fetch source metadata ──────────────────────────────────────────────────
    async with async_session_factory() as db:
        res = await db.execute(
            select(DataSource).where(DataSource.id == uuid.UUID(source_id))
        )
        source = res.scalar_one_or_none()
        if not source:
            return {"error": f"DataSource {source_id} not found"}

        file_path = source.file_path
        initial_schema = source.schema_json or {}
        indexing_mode = initial_schema.get("indexing_mode", "fast_text")
        context_hint = getattr(source, "context_hint", None)

    if not file_path or not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    try:
        # ── 1. Determine Strategy ──────────────────────────────────────────────
        strategy = recommend_strategy(file_path, indexing_mode="fast_text")
        
        _update_progress(source_id, initial_schema, 5,
                         f"Parsing document with strategy='{strategy}'...")

        # ── 2. Universal Partitioning ──────────────────────────────────────────
        partition_result = partition_document(file_path, strategy_override=strategy)

        logger.info("partitioning_done",
                    source_id=source_id,
                    total_elements=partition_result.total_elements,
                    has_tables=partition_result.has_tables,
                    has_images=partition_result.has_images,
                    has_code=partition_result.has_code,
                    page_count=partition_result.page_count)

        # ── 3. Filter to Text Chunks (Images handled by deep_vision flow) ──────
        text_chunks = get_text_chunks(partition_result)
        
        if not text_chunks:
            logger.warning("no_text_chunks_found", source_id=source_id,
                           file_type=partition_result.detected_file_type)
            return {
                "status": "success",
                "mode": "fast_text",
                "chunks": 0,
                "warning": "No extractable text found. Document may be image-only.",
                "indexing_mode": "fast_text",
            }

        _update_progress(source_id, initial_schema, 15,
                         f"Extracted {len(text_chunks)} elements. Embedding...")

        # ── 4. Embedding & Qdrant Upsert ──────────────────────────────────────
        embed_model = _get_embedding_model()
        collection_name = f"ds_{source_id.replace('-', '')}"
        qdrant = QdrantMultiVectorManager(collection_name=collection_name)
        await qdrant.ensure_collection(text_vector_size=768)

        processed_chunks = []
        for i, chunk in enumerate(text_chunks):
            text_vector = embed_model.embed_query(chunk.text)

            qdrant.upsert_page(
                page_id=chunk.chunk_id,
                text_vector=text_vector,
                metadata={
                    "source_id": source_id,
                    "page_num": chunk.page_num,
                    "chunk_index": chunk.chunk_index,
                    # Child — high precision for vector similarity search
                    "text": chunk.text,
                    # Parent — rich context for LLM synthesis
                    "parent_text": chunk.parent_text,
                    # Element type (Table, NarrativeText, Title, Code, etc.)
                    "element_type": chunk.element_type.value,
                    # Atomic flag — useful for retrieval filtering
                    "atomic": chunk.atomic,
                    "is_text_chunk": True,
                    "chunk_strategy": "element_aware_parent_child",
                    "doc_strategy": strategy,
                }
            )

            processed_chunks.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "page": chunk.page_num,
                "chunk_index": chunk.chunk_index,
                "embedding": text_vector,
                "element_type": chunk.element_type.value
            })

            # Progress reporting every 10 chunks
            if i % 10 == 0 and i > 0:
                progress = min(20 + int((i / len(text_chunks)) * 70), 92)
                _update_progress(source_id, initial_schema, progress,
                                 f"Indexing element {i}/{len(text_chunks)} "
                                 f"[{chunk.element_type.value}]")

        # ── 5. Neo4j Knowledge Graph Sync ─────────────────────────────────────
        try:
            from app.infrastructure.neo4j_adapter import Neo4jAdapter
            from app.modules.pdf.utils.taxonomy import get_document_taxonomy

            neo4j = Neo4jAdapter()
            neo4j_chunks = [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "page": chunk.page_num,
                    "chunk_index": chunk.chunk_index,
                    "element_type": chunk.element_type.value,
                }
                for chunk in text_chunks
            ]

            taxonomy = get_document_taxonomy(context_hint)
            await neo4j.batch_upsert_document_structure(
                source_id=source_id,
                document_id=source_id,
                chunks=neo4j_chunks,
                taxonomy=taxonomy,
            )
            logger.info("neo4j_sync_done", source_id=source_id,
                        chunks=len(neo4j_chunks))
        except Exception as neo_err:
            logger.warning("neo4j_sync_failed_secondary", error=str(neo_err))

        # ── 6. Final Status Update ─────────────────────────────────────────────
        async with async_session_factory() as db:
            from sqlalchemy import update
            await db.execute(
                update(DataSource)
                .where(DataSource.id == uuid.UUID(source_id))
                .values(
                    indexing_status="done",
                    schema_json={
                        **initial_schema,
                        "page_count": partition_result.page_count,
                        "chunk_count": len(text_chunks),
                        "total_elements": partition_result.total_elements,
                        "has_tables": partition_result.has_tables,
                        "has_images": partition_result.has_images,
                        "has_code": partition_result.has_code,
                        "indexed": True,
                        "indexing_mode": "fast_text",
                        "doc_strategy": strategy,
                        "detected_file_type": partition_result.detected_file_type,
                        "progress": 100,
                        "current_step": (
                            f"Universal indexing complete. "
                            f"{len(text_chunks)} elements indexed "
                            f"({'+ Tables' if partition_result.has_tables else ''}"
                            f"{'+ Code' if partition_result.has_code else ''})."
                        ),
                    },
                )
            )
            await db.commit()

        logger.info("universal_fast_indexing_done",
                    source_id=source_id,
                    chunks=len(text_chunks),
                    file_type=partition_result.detected_file_type)

        return {
            "status": "success",
            "mode": "fast_text",
            "chunks": len(text_chunks),
            "page_count": partition_result.page_count,
            "has_tables": partition_result.has_tables,
            "has_code": partition_result.has_code,
            "doc_strategy": strategy,
            "indexing_mode": "fast_text",
            "chunk_data": processed_chunks
        }

    except Exception as e:
        logger.error("fast_indexing_failed", source_id=source_id, error=str(e))
        async with async_session_factory() as db:
            from sqlalchemy import update
            await db.execute(
                update(DataSource)
                .where(DataSource.id == uuid.UUID(source_id))
                .values(indexing_status="failed", last_error=str(e))
            )
            await db.commit()
        return {"error": str(e), "status": "failed"}


# ── Internal Helpers ───────────────────────────────────────────────────────────

def _update_progress(source_id: str, initial_schema: Dict,
                     progress: int, step_msg: str) -> None:
    """Fire-and-forget sync progress update helper."""
    import asyncio
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource
    from sqlalchemy import update

    async def _do_update():
        async with async_session_factory() as db:
            await db.execute(
                update(DataSource)
                .where(DataSource.id == uuid.UUID(source_id))
                .values(schema_json={
                    **initial_schema,
                    "progress": progress,
                    "current_step": step_msg,
                })
            )
            await db.commit()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_do_update())
        else:
            loop.run_until_complete(_do_update())
    except Exception:
        pass  # Non-critical: progress updates should not block indexing
