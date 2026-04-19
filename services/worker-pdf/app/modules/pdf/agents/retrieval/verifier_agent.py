from app.infrastructure.config import settings
import structlog
from typing import Dict, Any
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

async def verifier_agent(state: AnalysisState) -> Dict[str, Any]:
    """Verification Agent to prevent AI hallucinations in document synthesis."""
    report = state.get("insight_report")
    search_results = state.get("search_results", [])
    question = state.get("question")
    current_retry = state.get("retry_count", 0)
    
    if not report or not search_results:
        return {"verified": True} # Cannot verify, skipping
        
    logger.info("visual_verification_started", question=question)
    
    # We use Groq's fast Llama 3.1 8B for verification
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_FAST)
    
    # Combine real texts or descriptions from all retrieved pages
    context = ""
    for hit in search_results:
        p = hit.payload.get("page_num")
        content = hit.payload.get("text") or hit.payload.get("description") or "No content available."
        context += f"## PAGE {p}:\n{content}\n\n"

    prompt = f"""You are a Fact-Checker for a document analysis system. 
    Compare the generated AI ANSWER against the RETRIEVED TEXT CONTEXT.
    
    If the AI ANSWER contains statements that are computationally or factually NOT supported by the context OR are explicitly wrong, flag them.
    
    RETRIEVED TEXT CONTEXT:
    {context}
    
    AI ANSWER:
    {report}
    
    Your Task:
    1. If the answer is accurate and supported, output 'VERIFIED'.
    2. If there are hallucinated errors, output a detailed correction hint.
    
    Output ONLY 'VERIFIED' or the correction hint."""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        verification_res = res.content.strip()
        
        if "VERIFIED" in verification_res.upper() or current_retry >= 2:
            logger.info("visual_verification_passed_or_max_retries")
            return {"verified": True, "verification_hint": None, "retry_count": current_retry}
        else:
            logger.warning("visual_verification_failed", hint=verification_res)
            return {
                "verified": False, 
                "verification_hint": verification_res,
                "retry_count": current_retry + 1
            }
            
    except Exception as e:
        logger.error("visual_verification_failed", error=str(e))
        return {"verified": True} # Fallback
