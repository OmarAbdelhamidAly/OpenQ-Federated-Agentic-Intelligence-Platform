from app.infrastructure.config import settings
import structlog
from typing import Dict, Any
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

async def query_refiner_agent(state: AnalysisState) -> Dict[str, Any]:
    """Rewrites the user's question to be more search-friendly and explicit."""
    question = state.get("question")
    history = state.get("history", [])
    
    logger.info("query_refinement_started", original_question=question)
    
    # We use Groq's fast Llama 3.1 8B for this pre-processing step
    llm = get_llm(temperature=0, model=settings.LLM_MODEL_FAST)
    
    history_context = ""
    if history:
        history_context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-3:]])

    prompt = f"""You are an expert Query Refiner. Your job is to rewrite the user's question to be more explicit and optimized for a PDF search engine.
    
    RULES:
    1. If the question refers to "it", "this", or "previous", use the chat history to resolve the reference.
    2. STRICT RULE: Maintain the ORIGINAL language of the current USER QUESTION. Do NOT translate the question.
    3. Keep domain-specific terms and proper nouns exactly as they are.
    4. Output ONLY the refined question. NO conversational filler.
    
    CHAT HISTORY:
    {history_context}
    
    USER QUESTION: {question}
    
    REFINED QUESTION:"""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        refined_question = res.content.strip()
        logger.info("query_refinement_completed", refined_question=refined_question)
        return {"question": refined_question, "original_question": question}
    except Exception as e:
        logger.error("query_refinement_failed", error=str(e))
        return {"question": question} # Fallback to original
