import os
import uuid
import torch
import structlog
import json
import base64
from typing import Any, Dict, List, Optional
from io import BytesIO
from pdf2image import convert_from_path
from colpali_engine.models import ColPali, ColPaliProcessor
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.database.postgres import async_session_factory
from app.infrastructure.llm import get_llm
from app.models.knowledge import Document, KnowledgeBase
from app.models.data_source import DataSource
from app.modules.pdf.utils.qdrant_multivector import QdrantMultiVectorManager
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = structlog.get_logger(__name__)

# Lazy load model to save memory if not called
_model = None
_processor = None

def get_colpali():
    global _model, _processor
    if _model is None:
        import psutil
        model_name = "vidore/colpali-v1.2"
        _processor = ColPaliProcessor.from_pretrained(model_name)

        available_gb = psutil.virtual_memory().available / (1024 ** 3)
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        logger.info("memory_info", available_gb=round(available_gb, 1), total_gb=round(total_gb, 1))

        if total_gb >= 12:
            # Production EKS / high-RAM machine: simple loading, GPU or CPU auto-selected
            logger.info("model_loading_strategy", strategy="production_auto")
            _model = ColPali.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            ).eval()
        else:
            # Local / memory-constrained: rely on OS swap instead of accelerate custom offload
            logger.info("model_loading_strategy", strategy="local_swap")
            _model = ColPali.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16,
                device_map="cpu",
                low_cpu_mem_usage=True,
            ).eval()
    return _model, _processor


async def _get_doc_context(kb_id: Optional[str] = None, source_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches the context_hint and company_profile for a given KB or Source.
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
                    return {
                        "hint": doc.context_hint,
                        "profile": doc.kb.tenant.company_profile if doc.kb and doc.kb.tenant else None
                    }
            elif source_id:
                query = select(DataSource).where(DataSource.id == uuid.UUID(source_id))
                res = await db.execute(query)
                src = res.scalar_one_or_none()
                if src:
                    return {
                        "hint": src.context_hint,
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
        model, processor = get_colpali()
        
        if kb_id:
            collection_name = f"kb_{str(kb_id).replace('-', '')}"
        else:
            collection_name = f"ds_{str(source_id).replace('-', '')}"
            
        qdrant = QdrantMultiVectorManager(collection_name=collection_name)
        await qdrant.ensure_collection()

        # 1. Encode Query
        with torch.no_grad():
            batch_query = processor.process_queries([question]).to(model.device)
            query_embeddings = model.forward(**batch_query)
            query_vector = query_embeddings[0].cpu().tolist()
            
        # 2. Search
        search_results = qdrant.client.query_points(
            collection_name=qdrant.collection_name,
            query=query_vector,
            using="colpali",
            limit=3,
            with_payload=True
        ).points

        if not search_results:
            return {
                "insight_report": "No relevant visual information found in the document.",
                "executive_summary": "Retrieved 0 relevant pages."
            }

        # 3. Context
        hint = state.get("context_hint")
        profile = None
        if not hint:
             ctx = await _get_doc_context(kb_id, source_id)
             hint = ctx.get("hint")
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
        expert_persona = f"an expert in {hint} documents" if hint else "an advanced Visual Document Analyst"
        
        history_arr = state.get("history", [])
        chat_history = "No previous conversational context."
        if history_arr:
            chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

        prompt_text = f"You are {expert_persona}.\n\nCONVERSATIONAL MEMORY:\n{chat_history}\n\nQUESTION: {question}\n\nProvide an answer based ONLY on the visual context provided. Answer in the same language as the user's question (e.g. if asked in Arabic, answer in Arabic):"
        
        content = [{"type": "text", "text": prompt_text}]
        for b64_img in base64_images:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}})

        # We MUST use a vision-capable model (Gemini) for this step
        llm = get_llm(temperature=0, model="gemini-1.5-flash")
        res = await llm.ainvoke([HumanMessage(content=content)])
        
        visual_context = [{"page_number": page_nums[i], "image_base64": f"data:image/jpeg;base64,{s}"} for i, s in enumerate(base64_images)]

        return {
            "insight_report": res.content,
            "executive_summary": f"Visual analysis completed. {len(search_results)} pages retrieved.",
            "visual_context": visual_context
        }

    except Exception as e:
        logger.error("colpali_rag_failed", error=str(e))
        return {"error": f"ColPali RAG failed: {str(e)}"}
