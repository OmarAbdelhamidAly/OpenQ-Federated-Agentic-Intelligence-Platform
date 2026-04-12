from app.infrastructure.config import settings
import structlog
from typing import Dict, Any
from app.infrastructure.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

async def chat_agent(state: AnalysisState) -> Dict[str, Any]:
    """Handles general conversational messages (hellos, thanks, how are you)."""
    question = state.get("question")
    history = state.get("history", [])
    
    logger.info("conversational_chat_started", question=question)
    
    # We use a friendly, fast model for chat
    llm = get_llm(temperature=0.7, model=settings.LLM_MODEL_PDF)
    
    history_context = ""
    if history:
        history_context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-3:]])

    prompt = f"""You are a helpful and professional AI assistant for document analysis. 
    The user is just chatting with you right now, not asking about a specific part of a document.
    Respond naturally and politely in the same language as the user.
    
    CHAT HISTORY:
    {history_context}
    
    USER MESSAGE: {question}
    
    YOUR RESPONSE:"""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        return {"insight_report": res.content, "executive_summary": "Conversational reply provided."}
    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        return {"insight_report": "Hello! How can I help you with your documents today?"}
