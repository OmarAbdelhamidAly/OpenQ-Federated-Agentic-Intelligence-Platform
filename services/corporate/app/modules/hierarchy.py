"""Router for Organizational Hierarchy management."""
from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database import get_db
from app.infrastructure.security import require_admin
from app.models import OrgNode

router = APIRouter(
    prefix="/hierarchy", 
    tags=["Organizational Structure"],
    dependencies=[Depends(require_admin)]
)

@router.post("/nodes", response_model=Dict[str, Any])
async def create_node(node_data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """Create a new department, branch, or team in the hierarchy."""
    parent_id = node_data.get("parent_id")
    parent_uuid = uuid.UUID(parent_id) if parent_id else None
    
    # Calculate Materialized Path
    path = ""
    if parent_uuid:
        parent_res = await db.execute(select(OrgNode).where(OrgNode.id == parent_uuid))
        parent = parent_res.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent node not found")
        path = f"{parent.path}.{parent_id}" if parent.path else parent_id
    
    new_node = OrgNode(
        tenant_id=uuid.UUID(node_data["tenant_id"]),
        parent_id=parent_uuid,
        name=node_data["name"],
        description=node_data.get("description"),
        node_type=node_data.get("node_type", "department"),
        path=path,
        metadata=node_data.get("metadata")
    )
    
    db.add(new_node)
    await db.commit()
    await db.refresh(new_node)
    
    return {"status": "node_created", "node": new_node}

@router.get("/nodes/{tenant_id}")
async def get_tenant_hierarchy(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the full organizational tree for a tenant."""
    res = await db.execute(
        select(OrgNode).where(OrgNode.tenant_id == uuid.UUID(tenant_id)).order_by(OrgNode.path)
    )
    return res.scalars().all()

@router.get("/nodes/{node_id}/children")
async def get_children(node_id: str, db: AsyncSession = Depends(get_db)):
    """Get direct sub-departments or teams."""
    res = await db.execute(select(OrgNode).where(OrgNode.parent_id == uuid.UUID(node_id)))
    return res.scalars().all()
