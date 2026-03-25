"""Pydantic schemas for System Policies."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SystemPolicyBase(BaseModel):
    name: str
    rule_type: str  # cleaning, compliance, security
    description: str


class SystemPolicyCreate(SystemPolicyBase):
    pass


class SystemPolicyResponse(SystemPolicyBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemPolicyListResponse(BaseModel):
    policies: List[SystemPolicyResponse]


class ResourcePolicyBase(BaseModel):
    principal_id: uuid.UUID
    action: str  # "query", "upload", "delete", "*"
    resource_id: str  # DataSource UUID or "pillar.*" or "*"
    effect: str = "allow"


class ResourcePolicyCreate(ResourcePolicyBase):
    pass


class ResourcePolicyResponse(ResourcePolicyBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourcePolicyListResponse(BaseModel):
    policies: List[ResourcePolicyResponse]
