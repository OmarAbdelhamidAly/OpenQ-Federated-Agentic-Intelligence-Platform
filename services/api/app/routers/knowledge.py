"""Router for managing knowledge bases and documents (the 'Contextual Data' RAG component)."""

import uuid
from typing import Annotated, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Form
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres import get_db
from app.infrastructure.api_dependencies import get_current_user, require_admin
from app.models.knowledge import KnowledgeBase, Document
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    DocumentResponse,
    DocumentListResponse
)
from app.infrastructure.adapters.storage import save_upload_file

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("/", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all knowledge bases for the current tenant."""
    # Subquery for document count
    doc_count_subquery = (
        select(Document.kb_id, func.count(Document.id).label("doc_count"))
        .group_by(Document.kb_id)
        .subquery()
    )
    
    result = await db.execute(
        select(KnowledgeBase, doc_count_subquery.c.doc_count)
        .outerjoin(doc_count_subquery, KnowledgeBase.id == doc_count_subquery.c.kb_id)
        .where(KnowledgeBase.tenant_id == current_user.tenant_id)
    )
    
    kb_list = []
    for kb, count in result.all():
        kb_resp = KnowledgeBaseResponse.model_validate(kb)
        kb_resp.document_count = count or 0
        kb_list.append(kb_resp)
        
    return {"knowledge_bases": kb_list}


@router.post("/", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_in: KnowledgeBaseCreate,
):
    """Create a new knowledge base (Admin only)."""
    new_kb = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        name=kb_in.name,
        description=kb_in.description,
    )
    db.add(new_kb)
    await db.commit()
    await db.refresh(new_kb)
    
    # Initialize collection in Qdrant (async-ish)
    try:
        from app.infrastructure.adapters.qdrant import qdrant_adapter
        # Qdrant client is sync in the adapter i made, so we just call it.
        # Collection name = tenant_id + kb_id
        collection_name = f"kb_{str(new_kb.id).replace('-', '')}"
        await qdrant_adapter.create_collection(collection_name)
    except Exception as e:
        logger.error("qdrant_collection_creation_failed", error=str(e), kb_id=str(new_kb.id))

    return new_kb


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a knowledge base and all its documents (Admin only)."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, 
            KnowledgeBase.tenant_id == current_user.tenant_id
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    await db.commit()
    
    # Optional: Delete Qdrant collection
    return None


@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    kb_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all documents in a knowledge base."""
    # Verify KB ownership
    kb_res = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == current_user.tenant_id))
    if not kb_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    result = await db.execute(select(Document).where(Document.kb_id == kb_id))
    return {"documents": result.scalars().all()}


@router.post("/{kb_id}/upload", response_model=DocumentResponse)
async def upload_document(
    kb_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    context_hint: Annotated[Optional[str], Form()] = None,
):
    """Upload a document to a knowledge base and trigger indexing."""
    # Verify KB ownership
    kb_res = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == current_user.tenant_id))
    if not kb_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Save file
    file_path = await save_upload_file(file, str(current_user.tenant_id))
    
    doc = Document(
        kb_id=kb_id,
        name=file.filename,
        file_path=file_path,
        context_hint=context_hint,
        status="pending"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # Trigger background indexing
    from app.worker import process_document_indexing
    process_document_indexing.delay(str(doc.id))
    
    return doc


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a specific document from a knowledge base (Admin only)."""
    # Verify doc exists and belongs to a KB owned by this tenant
    query = (
        select(Document)
        .join(KnowledgeBase)
        .where(
            Document.id == doc_id,
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id
        )
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    await db.delete(doc)
    await db.commit()
    
    # Optional: Delete from Qdrant if indexed
    # collection_name = f"kb_{str(kb_id).replace('-', '')}"
    # await qdrant_adapter.delete_points(collection_name, [str(doc_id)])
    
    return None
