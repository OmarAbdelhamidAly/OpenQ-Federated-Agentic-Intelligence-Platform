"""Router for Strategic Goals and Policies management."""
from __future__ import annotations
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database import get_db
from app.infrastructure.security import require_admin
from app.models import CorporateGoal, CorporatePolicy, TaskSubmission
from app.modules.strategic_agent import strategic_agent

router = APIRouter(
    prefix="/strategy", 
    tags=["Strategy & Governance"],
    dependencies=[Depends(require_admin)] # Entire router is Admin-only
)

# ── Goals Management ─────────────────────────────────────────────────────────

@router.post("/goals", response_model=Dict[str, Any])
async def create_goal(goal_data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    goal = CorporateGoal(
        tenant_id=uuid.UUID(goal_data["tenant_id"]),
        node_id=uuid.UUID(goal_data["node_id"]),
        title=goal_data["title"],
        description=goal_data.get("description"),
        target_date=goal_data.get("target_date"),
        priority=goal_data.get("priority", "medium"),
        metrics=goal_data.get("metrics")
    )
    db.add(goal)
    await db.commit()
    return {"status": "goal_created", "id": str(goal.id)}

@router.get("/goals/{node_id}")
async def list_node_goals(node_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CorporateGoal).where(CorporateGoal.node_id == uuid.UUID(node_id)))
    return res.scalars().all()

# ── Policies Management ──────────────────────────────────────────────────────

@router.post("/policies")
async def create_policy(policy_data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    policy = CorporatePolicy(
        tenant_id=uuid.UUID(policy_data["tenant_id"]),
        title=policy_data["title"],
        content=policy_data["content"],
        category=policy_data.get("category", "general"),
        severity=policy_data.get("severity", "warning"),
        node_id=uuid.UUID(policy_data["node_id"]) if policy_data.get("node_id") else None
    )
    db.add(policy)
    await db.commit()
    return {"status": "policy_created", "id": str(policy.id)}

# ── Strategic Analysis (The CFO Engine) ──────────────────────────────────────

@router.post("/analyze/{submission_id}")
async def analyze_submission_impact(submission_id: str):
    """
    Trigger a strategic impact analysis for a specific submission.
    This is where the Strategic Agent translates work into Business Value.
    """
    try:
        sub_uuid = uuid.UUID(submission_id)
        analysis_result = await strategic_agent.analyze_submission(sub_uuid)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=404, detail=analysis_result["error"])
            
        return {
            "status": "analysis_complete",
            "business_impact": analysis_result["analysis"],
            "meta": {
                "submission_id": submission_id,
                "agent": "Strategic Advisor v1.0"
            }
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid submission UUID")
