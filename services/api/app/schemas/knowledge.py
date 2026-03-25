"""Pydantic schemas for Knowledge Bases and Documents."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    name: str


class DocumentCreate(DocumentBase):
    kb_id: uuid.UUID
    context_hint: Optional[str] = None # 'invoice', 'legal', 'audit_report', etc.


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    kb_id: uuid.UUID
    status: str
    file_path: str
    metadata_json: Optional[Dict[str, Any]] = None
    context_hint: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseBase(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseResponse(KnowledgeBaseBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: List[KnowledgeBaseResponse]


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
