from app.infrastructure.config import settings
import structlog
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState
from app.modules.pdf.utils.procedural_memory import procedural_memory
from app.modules.pdf.utils.episodic_memory import episodic_memory

logger = structlog.get_logger(__name__)

class Recommendation(BaseModel):
    title: str = Field(description="Short title for the recommendation")
    description: str = Field(description="Detailed explanation of the recommendation")
    action: str = Field(description="A specific, actionable next step")

class AnalystOutput(BaseModel):
    executive_summary: str = Field(description="A professional executive summary of the document insights")
    recommendations: List[Recommendation] = Field(description="Exactly 3 actionable strategic recommendations")

async def analyst_agent(state: AnalysisState) -> Dict[str, Any]:
    """Analytical Agent to generate high-level insights and professional recommendations."""
    report = state.get("insight_report")
    
    if not report:
        return {}
        
    logger.info("analyst_insights_started")
    
    # We use Groq's fast Llama 3.1 8B for analysis
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_PDF)
    structured_llm = llm.with_structured_output(AnalystOutput)
    
    Previous Context:
    {running_summary}

    Past Experience (Similar Documents/Queries):
    {episodic_context}

    Procedural Guidelines:
    {procedural_skill}

    AI ANSWER:
    {report}
    """
    
    # Retrieve Episodic Experience
    past_exp = await episodic_memory.get_related_insights(state.get("tenant_id", "default"), state.get("question", ""))
    episodic_context = "No direct past experiences for this specific query."
    if past_exp:
        e = past_exp[0]
        episodic_context = f"In a previous analysis of {e['source_id']}, we found: {e['summary']}. Use this to ensure consistency."

    try:
        res = await structured_llm.ainvoke([HumanMessage(content=prompt.format(
            report=report,
            running_summary=state.get("running_summary", "No previous context."),
            episodic_context=episodic_context,
            procedural_skill=procedural_memory.get_procedural_knowledge(state.get("analysis_mode", "deep_vision"))
        ))])
        logger.info("analyst_insights_completed")
        
        # Convert Pydantic objects to generic dicts for state merging
        recommendations_list = [
            {"title": r.title, "description": r.description, "action": r.action} 
            for r in res.recommendations
        ]
        
        return {
            "executive_summary": res.executive_summary,
            "recommendations": recommendations_list,
        }
            
    except Exception as e:
        logger.error("analyst_insights_failed", error=str(e))
        return {
            "executive_summary": "Analysis completed. Review the findings above.", 
            "recommendations": [
                {
                    "title": "Review Required", 
                    "description": "The AI encountered an error while synthesizing strategic recommendations.", 
                    "action": "Please try submitting the query again."
                }
            ]
        }
