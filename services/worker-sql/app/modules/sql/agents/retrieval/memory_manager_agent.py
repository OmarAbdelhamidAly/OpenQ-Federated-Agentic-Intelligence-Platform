import structlog
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

logger = structlog.get_logger(__name__)

async def memory_manager_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Manages the sliding window memory for the Universal Analyst.
    
    1. Appends the latest interaction to chat_history.
    2. If history exceeds MAX_HISTORY, summarizes the oldest ones.
    3. Updates running_summary.
    """
    source_id = state.get("source_id")
    logger.info("memory_manager_agent_started", source_id=source_id)
    
    question_text = state.get("question", "")
    insight_report = state.get("insight_report", "")
    
    # Load previously accumulated history from state
    current_history = state.get("chat_history") or []
    
    # Append the latest turn
    if question_text:
        current_history.append({"role": "user", "content": question_text})
    if insight_report:
        current_history.append({"role": "assistant", "content": insight_report})
    
    # Sliding Window Configuration
    MAX_HISTORY = 4 # Keep last 2 full conversation turns
    running_summary = state.get("running_summary", "")
    
    new_history = current_history
    
    if len(current_history) > MAX_HISTORY:
        fallen_messages = current_history[:-MAX_HISTORY]
        new_history = current_history[-MAX_HISTORY:]
        
        # Summarize fallen messages combined with old running summary
        fallen_text = "\n".join([f"{msg['role'].upper()}: {msg.get('content', '')}" for msg in fallen_messages])
        
        # Use centralized LLM factory with specific instructions for summarization
        llm = get_llm(temperature=0, model_name="meta-llama/llama-3.1-8b-instruct")
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI memory archivist. Condense the past conversation into a succinct running summary. "
                       "Combine the existing summary (if any) with the newly provided older chat logs to form ONE cohesive paragraph. "
                       "Retain crucial context (e.g. important entities, tables discussed, main analytical context). "
                       "Only output the summary text, nothing else."),
            ("user", f"Existing Summary: {running_summary}\n\nOlder logs to integrate:\n{fallen_text}")
        ])
        
        try:
            res = await prompt.pipe(llm).ainvoke({})
            running_summary = str(res.content if hasattr(res, 'content') else res)
            logger.info("memory_summary_updated", source_id=source_id)
        except Exception as e:
            logger.error("memory_summary_failed", error=str(e))
    
    logger.info("memory_manager_agent_finished", history_length=len(new_history))
    
    return {
        "chat_history": new_history,
        "running_summary": running_summary
    }
