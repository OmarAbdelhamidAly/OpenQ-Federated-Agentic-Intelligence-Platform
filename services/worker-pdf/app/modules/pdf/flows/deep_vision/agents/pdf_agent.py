from app.infrastructure.config import settings
import os
import uuid
import structlog
import json
import base64
from typing import Any, Dict, List, Optional
from io import BytesIO
from pdf2image import convert_from_path
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.database.postgres import async_session_factory
from app.infrastructure.llm import get_llm
from app.models.knowledge import Document, KnowledgeBase
from app.models.data_source import DataSource
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from app.modules.pdf.flows.deep_vision.agents.indexing_agent import _get_embedding_model
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = structlog.get_logger(__name__)

# No local models needed for Groq Vision flow


async def _get_doc_context(kb_id: Optional[str] = None, source_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches the context_hint, industry, and company_profile for a given KB or Source.
    """
    try:
        async with async_session_factory() as db:
            if kb_id:
                query = (
                    select(Document)
                    .options(
                        selectinload(Document.kb).selectinload(KnowledgeBase.tenant)
                    )
                    .where(Document.kb_id == uuid.UUID(kb_id))
                    .order_by(Document.created_at.desc())
                )
                res = await db.execute(query)
                doc = res.scalars().first()
                if doc:
                    metadata = doc.metadata_json or {}
                    dna = metadata.get("dna", {})
                    return {
                        "hint": doc.context_hint,
                        "industry": dna.get("industry", "General Business"),
                        "profile": doc.kb.tenant.company_profile if doc.kb and doc.kb.tenant else None
                    }
            elif source_id:
                query = select(DataSource).where(DataSource.id == uuid.UUID(source_id))
                res = await db.execute(query)
                src = res.scalar_one_or_none()
                if src:
                    schema = src.schema_json or {}
                    metadata = schema.get("metadata", {})
                    return {
                        "hint": src.context_hint,
                        "industry": metadata.get("industry", "General Business"),
                        "profile": None
                    }
            return {}
    except Exception as e:
        logger.warning("context_fetch_failed", error=str(e))
        return {}


async def colpali_retrieval_agent(state: AnalysisState) -> Dict[str, Any]:
    """Uses ColPali to encode query and retrieve document context via Qdrant."""
    kb_id = state.get("kb_id")
    source_id = state.get("source_id")
    question = state.get("question")
    
    if not kb_id and not source_id:
        return {"error": "No Knowledge Base or Source ID provided for PDF RAG."}

    try:
        # 1. Initialize models
        embed_model = _get_embedding_model()
        
        if kb_id:
            collection_name = f"kb_{str(kb_id).replace('-', '')}"
        else:
            collection_name = f"ds_{str(source_id).replace('-', '')}"
            
        qdrant = QdrantMultiVectorManager(collection_name=collection_name)
        # await qdrant.ensure_collection() # Indexing should have done this

        # 2. Encode Query
        query_vector = embed_model.embed_query(question)
            
        # 3. Search via Text Description
        search_results = qdrant.search_text(
            query_vector=query_vector,
            limit=3
        )

        if not search_results:
            return {
                "insight_report": "No relevant visual information found in the document.",
                "executive_summary": "Retrieved 0 relevant pages."
            }

        # 3. Context
        hint = state.get("context_hint")
        industry = state.get("industry")
        profile = None
        if not hint or not industry:
             ctx = await _get_doc_context(kb_id, source_id)
             hint = ctx.get("hint")
             industry = ctx.get("industry", "General Business")
             profile = ctx.get("profile")

        # 4. Extract Images
        page_nums = []
        full_path = None
        
        async with async_session_factory() as db:
            # Determine path from the first result or state
            hit = search_results[0]
            hit_doc_id = hit.payload.get("doc_id")
            hit_source_id = hit.payload.get("source_id")
            
            if hit_doc_id:
                doc_res = await db.execute(select(Document).where(Document.id == uuid.UUID(hit_doc_id)))
                obj = doc_res.scalars().first()
                if obj: full_path = obj.file_path
            elif hit_source_id:
                src_res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(hit_source_id)))
                obj = src_res.scalar_one_or_none()
                if obj: full_path = obj.file_path
            elif source_id:
                src_res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
                obj = src_res.scalar_one_or_none()
                if obj: full_path = obj.file_path

            if full_path and os.path.exists(full_path):
                for hit in search_results:
                    p = hit.payload.get("page_num")
                    if p: page_nums.append(p)
                
                page_nums = sorted(list(set(page_nums)))
                images = convert_from_path(full_path, dpi=120)
                
                base64_images = []
                for p in page_nums:
                    idx = p - 1
                    if 0 <= idx < len(images):
                        buffered = BytesIO()
                        images[idx].save(buffered, format="JPEG", quality=75)
                        base64_images.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))

        # 5. Synthesis
        expert_persona = f"an expert in {industry} documents" if industry else "an advanced Visual Document Analyst"
        
        history_arr = state.get("history", [])
        chat_history = "No previous conversational context."
        if history_arr:
            chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

        prompt_text = f"""You are {expert_persona}.

CONVERSATIONAL MEMORY:
{chat_history}

QUESTION: {question}

Provide an answer based ONLY on the visual context provided. Answer in the same language as the user's question (e.g. if asked in Arabic, answer in Arabic):"""
        
        content = [{"type": "text", "text": prompt_text}]
        for b64_img in base64_images:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}})

        # We now use Groq Llama 3.2 Vision for maximum speed and performance
        llm = get_llm(temperature=0, model=settings.LLM_MODEL_VISION)
        res = await llm.ainvoke([HumanMessage(content=content)])
        
        visual_context = [{"page_number": page_nums[i], "image_base64": f"data:image/jpeg;base64,{s}"} for i, s in enumerate(base64_images)]

        return {
            "insight_report": res.content,
            "executive_summary": f"Visual analysis completed. {len(search_results)} pages retrieved.",
            "visual_context": visual_context,
            "industry": industry
        }

    except Exception as e:
        logger.error("colpali_rag_failed", error=str(e))
        return {"error": f"ColPali RAG failed: {str(e)}"}
