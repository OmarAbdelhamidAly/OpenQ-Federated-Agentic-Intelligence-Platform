"""PDF Indexing Agent — Vision-based ingestion using ColPali patches."""
import os
import uuid
import gc
import base64
import structlog
from io import BytesIO
from typing import Any, Dict, List, Optional
from PIL import Image
from pdf2image import convert_from_path, pdfinfo_from_path
from langchain_core.messages import HumanMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.infrastructure.llm import get_llm
from app.infrastructure.database.postgres import async_session_factory
from app.models.knowledge import Document, KnowledgeBase
from app.models.tenant import Tenant
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.modules.pdf.utils.taxonomy import get_document_taxonomy
from sqlalchemy import select, update as sql_update
from sqlalchemy.orm import selectinload

logger = structlog.get_logger(__name__)

# ── Lazy singletons ────────────────────────────────────────────────────────────
_embed_model = None

def _get_embedding_model():
    """Returns local Embeddings via FastEmbed.
    
    Bypassing Gemini embeddings because Google AI Studio returns 404/geo-blocks,
    and OpenRouter isn't available. FastEmbed is already installed in requirements.txt.
    """
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    
    # Defaults to BAAI/bge-small-en-v1.5 which is 384 dimensions natively
    # To match our 768 vector size, we will use nomic-ai/nomic-embed-text-v1.5
    return FastEmbedEmbeddings(
        model_name="nomic-ai/nomic-embed-text-v1.5" # 768 dimensions
    )

# --- Centralized Taxonomy Moved to app.modules.pdf.utils.taxonomy ---

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
    
    # 1. Direct Slug Lookup (Fastest/Deterministic via Central taxonomy)
    static_meta = get_document_taxonomy(hint)
    return {
        "doc_type": static_meta["doc_type"],
        "industry": static_meta["industry"],
        "source_hint": hint or "none",
        "dna": {"summary": f"Strategic {static_meta['doc_type']} identified in {static_meta['industry']} domain."},
        "specialized_fields": {
            "classification_mode": "taxonomy_direct",
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

async def _build_dynamic_metadata_with_ai(
    vision_llm: Any, 
    page_descriptions: list[str], 
    context_hint: Optional[str] = None
) -> Dict[str, Any]:
    """Generates a high-impact summary of the document using the collected page descriptions."""
    
    # Use only the first few and last few pages to keep context window safe if the doc is huge
    content_sample = "\n---\n".join(page_descriptions[:5])
    if len(page_descriptions) > 5:
         content_sample += "\n... [Middle pages omitted for summary] ...\n" + "\n---\n".join(page_descriptions[-2:])

    prompt = f"""You are an Expert Document Librarian. 
    Analyze the following page-by-page visual descriptions of a document and provide a highly descriptive 1-sentence summary that highlights the document's main topic, purpose, and key entities.
    
    Context Hint: {context_hint or 'None'}
    
    Document Descriptions:
    {content_sample}
    
    Respond with ONLY the 1-sentence summary. No preamble."""
    
    try:
        res = await vision_llm.ainvoke(prompt)
        summary = res.content.strip()
    except Exception as e:
        logger.warning(f"ai_summary_generation_failed, falling back: {str(e)}")
        summary = f"A {len(page_descriptions)}-page document analyzed via vision."

    # Get base metadata
    base_meta = _build_static_metadata(context_hint)
    
    # Inject the smart summary
    base_meta["dna"]["summary"] = summary
    base_meta["specialized_fields"]["classification_mode"] = "ai_vision_synthesis"
    
    return base_meta



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
            # Fetch current metadata to preserve it during updates
            initial_meta = doc.metadata_json or {}
            
            result = await _run_indexing_core(
                id_for_meta=str(doc.id),
                file_path=file_path,
                kb_id=kb_id,
                context_hint=context_hint,
                is_source=False,
                initial_schema=initial_meta
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
            # Fetch current schema to preserve it during updates
            initial_schema = source.schema_json or {}
            
            result = await _run_indexing_core(
                id_for_meta=str(source.id),
                file_path=file_path,
                kb_id=None, # Direct uploads don't have kb_id
                context_hint=context_hint,
                is_source=True,
                initial_schema=initial_schema
            )
            
            # Optionally update source metadata
            source.schema_json = {
                **initial_schema,
                "page_count": result.get("pages"),
                "indexed": True,
                "metadata": result.get("metadata"),
                "progress": 100,
                "current_step": "Vision indexing complete. Neural map finalized."
            }
            source.indexing_status = "done"
            await db.commit()
            return {"status": "success", "pages_indexed": result.get("pages")}
            
        except Exception as e:
            logger.error("source_indexing_failed", source_id=source_id, error=str(e))
            async with async_session_factory() as db2:
                from sqlalchemy import update
                await db2.execute(
                    sql_update(DataSource)
                    .where(DataSource.id == uuid.UUID(source_id))
                    .values(indexing_status="failed", last_error=str(e))
                )
                await db2.commit()
            return {"error": str(e)}

async def _run_indexing_core(
    id_for_meta: str, 
    file_path: str, 
    kb_id: Optional[uuid.UUID], 
    context_hint: Optional[str], 
    is_source: bool,
    initial_schema: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Core logic to index a PDF file into Qdrant using Groq Vision."""
    if initial_schema is None:
        initial_schema = {}
        
    if not file_path or not os.path.exists(file_path):
        raise ValueError(f"File not found at {file_path}")

    # Get page count to process page-by-page (Memory Efficiency)
    info = pdfinfo_from_path(file_path)
    total_pages = info["Pages"]
    
    # 1. Initialize Models
    from langchain_google_genai import ChatGoogleGenerativeAI
    import asyncio
    from app.infrastructure.config import settings
    
    # Priority 1: OpenRouter (Fast, cheap, no limits - when funded)
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    primary_vision = ChatOpenAI(
        model="google/gemini-2.0-flash-001", 
        temperature=0,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://insightify.ai",
            "X-Title": "Insightify Business Intelligence Assistant"
        }
    )
    
    # Priority 2: Gemini Direct API (Free tier, slow with rate limits)
    fallback_vision = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp", 
        temperature=0,
        google_api_key=settings.GEMINI_API_KEY
    )
    
    # Automatically switch to Free Gemini if OpenRouter rejects (e.g. 402 Insufficient Balance)
    vision_llm = primary_vision.with_fallbacks([fallback_vision])
    embed_model = _get_embedding_model()
    
    # 2. Collection Setup
    if kb_id:
        collection_name = f"kb_{str(kb_id).replace('-', '')}"
    else:
        collection_name = f"ds_{str(id_for_meta).replace('-', '')}"
        
    qdrant = QdrantMultiVectorManager(collection_name=collection_name)
    await qdrant.ensure_collection(text_vector_size=768) # embedding-001 is 768-dim

    # 3. Processing Loop
    all_page_descriptions = []
    for current_page in range(1, total_pages + 1):
        logger.info(f"Processing PDF page {current_page} of {total_pages} (Groq Vision)...")
        
        # Render single page
        images = convert_from_path(
            file_path, 
            dpi=72, 
            first_page=current_page, 
            last_page=current_page
        )
        if not images:
            continue
        page_image = images[0]
        
        # Enforce Groq's absolute max resolution of 1120x1120
        page_image.thumbnail((1120, 1120))
        
        # Update progress
        progress = int((current_page / total_pages) * 98)
        async with async_session_factory() as db:
            update_data = {
                "progress": progress, 
                "current_step": f"Groq Vision Analysis: Page {current_page} of {total_pages}",
                "page_count": total_pages
            }
            if is_source:
                from app.models.data_source import DataSource
                await db.execute(sql_update(DataSource).where(DataSource.id == uuid.UUID(id_for_meta)).values(schema_json={**initial_schema, **update_data}))
            else:
                from app.models.knowledge import Document
                await db.execute(sql_update(Document).where(Document.id == uuid.UUID(id_for_meta)).values(metadata_json={**initial_schema, **update_data}))
            await db.commit()

        # A. Vision Analysis via Groq
        buffered = BytesIO()
        page_image.save(buffered, format="JPEG", quality=80)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        prompt = "Extract all text, tables, and key visual elements from this document page. Provide a structured, searchable description. Focus on content that a user might search for."
        
        # Throttle removed — OpenRouter is active and funded.
        
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
        ])
        
        try:
            res = await vision_llm.ainvoke([message])
            page_description = res.content
        except Exception as e:
            logger.error("groq_vision_failed", page=current_page, error=str(e))
            page_description = f"Error analyzing page {current_page}. Vision API failed."

        # B. Embedding Generation
        text_vector = embed_model.embed_query(page_description)
        
        # C. Qdrant Sync
        page_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{id_for_meta}_{current_page}")
        qdrant.upsert_page(
            page_id=str(page_uuid),
            text_vector=text_vector,
            metadata={
                "doc_id": id_for_meta if not is_source else None,
                "source_id": id_for_meta if is_source else None,
                "kb_id": str(kb_id) if kb_id else None,
                "page_num": current_page,
                "description": page_description, # Store description for context
                "is_header_page": current_page == 1
            }
        )
        
        # Memory Cleanup
        all_page_descriptions.append(page_description)
        gc.collect()

    # ── Neo4j Knowledge Graph Sync (Universal Synthesis Layer) ──────
    try:
        from app.infrastructure.neo4j_adapter import Neo4jAdapter
        neo4j = Neo4jAdapter()
        
        neo4j_chunks = []
        for i, desc in enumerate(all_page_descriptions):
            page_num = i + 1
            neo4j_chunks.append({
                "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{id_for_meta}_{page_num}")),
                "text": desc,
                "page": page_num,
                "chunk_index": i
            })
        
        await neo4j.batch_upsert_document_structure(
            source_id=id_for_meta,
            document_id=id_for_meta,
            chunks=neo4j_chunks,
            taxonomy=doc_dna # Pass taxonomy to Neo4j
        )
        logger.info("neo4j_vision_sync_done", source_id=id_for_meta, chunks=len(neo4j_chunks))
    except Exception as neo_err:
        logger.warning("neo4j_vision_sync_failed_secondary", error=str(neo_err))

    # Create Dynamic AI Metadata
    doc_dna = await _build_dynamic_metadata_with_ai(
        vision_llm=vision_llm,
        page_descriptions=all_page_descriptions,
        context_hint=context_hint
    )
    
    # Final update for completion
    async with async_session_factory() as db:
        if is_source:
            from app.models.data_source import DataSource
            await db.execute(
                sql_update(DataSource)
                .where(DataSource.id == uuid.UUID(id_for_meta))
                .values(schema_json={
                    **initial_schema,
                    "progress": 100, 
                    "current_step": "Vision indexing complete. Neural map finalized.",
                    "page_count": total_pages,
                    "metadata": doc_dna
                })
            )
        else:
            from app.models.knowledge import Document
            await db.execute(
                sql_update(Document)
                .where(Document.id == uuid.UUID(id_for_meta))
                .values(metadata_json={
                    **initial_schema,
                    "progress": 100, 
                    "current_step": "Vision indexing complete. Neural map finalized.",
                    "page_count": total_pages,
                    "dna": doc_dna
                })
            )
        await db.commit()

    return {"pages": total_pages, "metadata": doc_dna}
