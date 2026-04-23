"""Use case to analyze a corporate submission for strategic alignment."""
from __future__ import annotations
import uuid
from typing import Dict, Any
import structlog

from app.infrastructure.database.repository import CorporateRepository
from app.modules.strategic_agent import StrategicAgent # We keep the agent as a tool

logger = structlog.get_logger(__name__)

class AnalyzeSubmissionUseCase:
    def __init__(self, repo: CorporateRepository, agent: StrategicAgent):
        self.repo = repo
        self.agent = agent

    async def execute(self, submission_id: uuid.UUID) -> Dict[str, Any]:
        """Execute the strategic analysis process."""
        # 1. Fetch context via repository (Infrastructure)
        context = await self.repo.get_submission_context(submission_id)
        if not context:
            return {"error": "Submission context not found"}

        # 2. Perform AI analysis (Tool/Agent)
        # We can pass the context directly to the agent instead of let it fetch its own data
        analysis_prompt = self.agent._build_prompt(
            context["submission"], 
            context["task"], 
            context["goals"], 
            context["policies"]
        )
        
        # In a strict Clean Arch, the agent would be an interface
        # For now, we call the LLM through the agent
        logger.info("executing_strategic_analysis_use_case", submission_id=str(submission_id))
        
        from langchain_core.messages import HumanMessage, SystemMessage
        response = await self.agent.llm.ainvoke([
            SystemMessage(content="You are a Senior Strategic Advisor and Compliance Officer."),
            HumanMessage(content=analysis_prompt)
        ])

        return {
            "submission_id": str(submission_id),
            "analysis": response.content,
            "alignment_score": self._extract_score(response.content)
        }

    def _extract_score(self, text: str) -> int:
        """Heuristic to extract alignment score from LLM text."""
        import re
        match = re.search(r"Alignment Score:\s*(\d+)", text)
        return int(match.group(1)) if match else 85
