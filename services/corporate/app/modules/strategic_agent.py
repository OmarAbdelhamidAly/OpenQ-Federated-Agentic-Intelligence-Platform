"""Strategic Agent for Corporate Intelligence.

Analyzes submissions against organizational goals and policies.
"""
from __future__ import annotations
import structlog
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.config import settings
from app.infrastructure.database import async_session_factory
from app.models import CorporateGoal, CorporatePolicy, TaskSubmission, CorporateTask, OrgNode

logger = structlog.get_logger(__name__)


class StrategicAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL_STRATEGIC,
            temperature=0.1,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://openq.ai",
                "X-Title": "OpenQ Corporate Strategic Agent",
            },
        )

    async def analyze_submission(self, submission_id: uuid.UUID) -> Dict[str, Any]:
        """Perform strategic alignment and compliance analysis on a submission."""
        async with async_session_factory() as db:
            # 1. Fetch Submission and context
            submission_res = await db.execute(
                select(TaskSubmission).where(TaskSubmission.id == submission_id)
            )
            submission = submission_res.scalar_one_or_none()
            if not submission:
                return {"error": "Submission not found"}

            task_res = await db.execute(
                select(CorporateTask).where(CorporateTask.id == submission.task_id)
            )
            task = task_res.scalar_one_or_none()
            
            node_res = await db.execute(
                select(OrgNode).where(OrgNode.id == task.assignee_node_id)
            )
            node = node_res.scalar_one_or_none()

            # 2. Fetch Goals for this node (and parent nodes if needed)
            goals_res = await db.execute(
                select(CorporateGoal).where(
                    (CorporateGoal.node_id == node.id) & 
                    (CorporateGoal.status == "active")
                )
            )
            goals = goals_res.scalars().all()

            # 3. Fetch Policies
            policies_res = await db.execute(
                select(CorporatePolicy).where(
                    (CorporatePolicy.node_id == node.id) | (CorporatePolicy.node_id == None)
                )
            )
            policies = policies_res.scalars().all()

            # 4. Prepare Analysis Prompt
            analysis_prompt = self._build_prompt(submission, task, goals, policies)

            # 5. Run LLM
            logger.info("strategic_analysis_started", submission_id=str(submission_id))
            response = await self.llm.ainvoke([
                SystemMessage(content="You are a Senior Strategic Advisor and Compliance Officer."),
                HumanMessage(content=analysis_prompt)
            ])
            
            # 6. Parse and return result
            # (In a real scenario, we'd use structured output)
            result = {
                "submission_id": str(submission_id),
                "analysis": response.content,
                "timestamp": submission.submitted_at.isoformat() if submission.submitted_at else None
            }
            
            logger.info("strategic_analysis_complete", submission_id=str(submission_id))
            return result

    def _build_prompt(
        self, 
        submission: TaskSubmission, 
        task: CorporateTask, 
        goals: List[CorporateGoal], 
        policies: List[CorporatePolicy]
    ) -> str:
        goal_text = "\n".join([f"- {g.title}: {g.description}" for g in goals]) or "No specific goals defined."
        policy_text = "\n".join([f"- [{p.severity}] {p.title}: {p.content}" for p in policies]) or "No specific policies defined."
        
        return f"""Analyze the following task submission for strategic alignment and compliance.

### ORGANIZATIONAL CONTEXT
Active Goals:
{goal_text}

Relevant Policies:
{policy_text}

### TASK DETAILS
Title: {task.title}
Description: {task.description}

### SUBMISSION CONTENT
{submission.content or "No text content."}
Attachments Metadata: {submission.attachments}

### INSTRUCTIONS
1. **Strategic Alignment**: How well does this submission contribute to the active goals? Provide an Alignment Score (0-100).
2. **Compliance**: Does this submission violate any of the listed policies? Flag any critical issues.
3. **Strategic Recommendations**: What next steps should the department take based on this work?
4. **Summary**: Provide a concise summary for executive review.

Return your analysis in a professional, structured format."""

strategic_agent = StrategicAgent()
