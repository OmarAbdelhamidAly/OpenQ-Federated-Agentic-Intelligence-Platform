"""Repository for Corporate database operations."""
from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from app.infrastructure.database import async_session_factory
from app.models import OrgNode, CorporateGoal, CorporatePolicy, TaskSubmission, CorporateTask

class CorporateRepository:
    async def get_submission_context(self, submission_id: uuid.UUID) -> Dict[str, Any]:
        """Fetch submission, task, node, goals, and policies in one context."""
        async with async_session_factory() as db:
            submission = (await db.execute(select(TaskSubmission).where(TaskSubmission.id == submission_id))).scalar_one_or_none()
            if not submission: return {}
            
            task = (await db.execute(select(CorporateTask).where(CorporateTask.id == submission.task_id))).scalar_one_or_none()
            node = (await db.execute(select(OrgNode).where(OrgNode.id == task.assignee_node_id))).scalar_one_or_none()
            
            goals = (await db.execute(select(CorporateGoal).where(CorporateGoal.node_id == node.id))).scalars().all()
            policies = (await db.execute(select(CorporatePolicy).where((CorporatePolicy.node_id == node.id) | (CorporatePolicy.node_id == None)))).scalars().all()
            
            return {
                "submission": submission,
                "task": task,
                "node": node,
                "goals": goals,
                "policies": policies
            }

    async def get_all_nodes(self) -> List[OrgNode]:
        async with async_session_factory() as db:
            res = await db.execute(select(OrgNode))
            return res.scalars().all()
