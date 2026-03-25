"""Router for Team Group management."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.api_dependencies import get_db, get_current_user
from app.models.user import User
from app.models.team_group import TeamGroup
from app.schemas.group import GroupResponse, GroupCreateRequest, GroupUpdateRequest, GroupListResponse

router = APIRouter(prefix="/groups", tags=["Groups & Teams"])


@router.get("", response_model=List[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all groups within the current tenant."""
    # Subquery to count members per group
    count_sub = (
        select(User.group_id, func.count(User.id).label("cnt"))
        .where(User.tenant_id == current_user.tenant_id)
        .group_by(User.group_id)
        .subquery()
    )
    
    stmt = (
        select(TeamGroup, func.coalesce(count_sub.c.cnt, 0))
        .outerjoin(count_sub, TeamGroup.id == count_sub.c.group_id)
        .where(TeamGroup.tenant_id == current_user.tenant_id)
    )
    
    result = await db.execute(stmt)
    groups = []
    for group_obj, member_count in result:
        res = GroupResponse.model_validate(group_obj)
        res.member_count = member_count
        groups.append(res)
        
    return groups


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin creates a new organizational group."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create groups")
        
    new_group = TeamGroup(
        tenant_id=current_user.tenant_id,
        name=request.name,
        description=request.description,
        permissions=request.permissions
    )
    db.add(new_group)
    await db.commit()
    await db.refresh(new_group)
    return GroupResponse.model_validate(new_group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin deletes a group and unassigns its members."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete groups")
        
    # Check existence
    stmt = select(TeamGroup).where(TeamGroup.id == group_id, TeamGroup.tenant_id == current_user.tenant_id)
    res = await db.execute(stmt)
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
        
    # Unassign users first
    await db.execute(
        update(User)
        .where(User.group_id == group_id)
        .values(group_id=None)
    )
    
    await db.delete(group)
    await db.commit()
    return None
