"""Router for Corporate Tasks and Submissions."""
from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database import get_db
from app.infrastructure.security import require_admin, require_user
from app.models import CorporateTask, TaskSubmission, OrgNode

router = APIRouter(prefix="/tasks", tags=["Task Management"])

@router.post("/")
async def create_task(
    task_data: Dict[str, Any], 
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin)
):
    """Create a task and assign it to an organizational node (department/team)."""
    new_task = CorporateTask(
        tenant_id=uuid.UUID(task_data["tenant_id"]),
        creator_id=uuid.UUID(task_data["creator_id"]),
        assignee_node_id=uuid.UUID(task_data["assignee_node_id"]),
        title=task_data["title"],
        description=task_data.get("description"),
        deadline=task_data.get("deadline"),
        priority=task_data.get("priority", "medium"),
        status="active"
    )
    db.add(new_task)
    await db.commit()
    return {"status": "task_assigned", "id": str(new_task.id)}

@router.post("/{task_id}/submit")
async def submit_task_work(
    task_id: str, 
    submission_data: Dict[str, Any], 
    db: AsyncSession = Depends(get_db),
    _user = Depends(require_user)
):
    """Employee submits work against an assigned task."""
    submission = TaskSubmission(
        task_id=uuid.UUID(task_id),
        submitter_id=uuid.UUID(submission_data["submitter_id"]),
        content=submission_data.get("content"),
        attachments=submission_data.get("attachments")
    )
    db.add(submission)
    
    # Update task status
    task_res = await db.execute(select(CorporateTask).where(CorporateTask.id == uuid.UUID(task_id)))
    task = task_res.scalar_one_or_none()
    if task:
        task.status = "submitted"
        
    await db.commit()
    return {"status": "work_submitted", "submission_id": str(submission.id)}

@router.get("/node/{node_id}")
async def get_node_tasks(node_id: str, db: AsyncSession = Depends(get_db)):
    """Get all tasks assigned to a specific department or team."""
    res = await db.execute(select(CorporateTask).where(CorporateTask.assignee_node_id == uuid.UUID(node_id)))
    return res.scalars().all()
