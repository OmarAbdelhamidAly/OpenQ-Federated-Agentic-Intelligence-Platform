import uuid
import structlog
from typing import Any, Dict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.infrastructure.config import settings
from app.infrastructure.llm import get_llm
from app.schemas.nexus_state import NexusState

logger = structlog.get_logger(__name__)

async def query_fusion_node(state: NexusState) -> Dict[str, Any]:
    """Break down a complex user question into 3 domain-targeted sub-queries."""
    log = logger.bind(job_id=state.get("job_id"), node="query_fusion")
    log.info("decomposing_strategic_intent")

    llm = get_llm(temperature=0, model=settings.LLM_MODEL_NEXUS)

    parser = JsonOutputParser()
    prompt = PromptTemplate(
        template="""You are an Expert System Architect. Break down this question into 3 targeted sub-queries:
        1. Structural (Code/Architecture)
        2. Data Schema (SQL/Tables)
        3. Business Logic (Documents/Policy)

        Question: {question}
        {format_instructions}""",
        input_variables=["question"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    try:
        chain = prompt | llm | parser
        queries = await chain.ainvoke({"question": state["question"]})
        if not isinstance(queries, list):
            queries = [state["question"]]
    except Exception as e:
        log.warning("fusion_parsing_failed", error=str(e))
        queries = [state["question"]]

    return {
        "fusion_queries": queries,
        "thinking_steps": state.get("thinking_steps", []) + [{
            "node": "Strategic Intent Breakdown",
            "status": f"Generated {len(queries)} specialized sub-queries",
            "timestamp": str(uuid.uuid4())
        }]
    }
