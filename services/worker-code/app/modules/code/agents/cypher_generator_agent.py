import os
import structlog
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import CodeAnalysisState
from app.infrastructure.config import settings
from app.modules.code.utils.procedural_memory import procedural_memory
from app.modules.code.utils.episodic_memory import episodic_memory

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
# Key changes from the original:
#   - Schema now reflects the new property set (chunk_id, line_start, line_end
#     instead of `code`).
#   - Added explicit guidance on using the full-text index for name search.
#   - Added guidance to use LIMIT for potentially large result sets.
#   - Markdown fence stripping moved to a dedicated helper to keep the agent
#     body readable.
# ---------------------------------------------------------------------------
PROMPT = """\
You are an expert Neo4j Cypher developer analysing a codebase knowledge graph.
Generate a single valid Cypher query that answers the user's question, taking into account the context of the previous conversation.

Previous Conversation Context:
{running_summary}

User's Latest Question:
{question}

STRICT RULES:
1. Return ONLY the raw Cypher query — no markdown, no ``` fences, no commentary.
2. ALWAYS filter by: WHERE n.source_id = $source_id  (parameter name: $source_id).
3. The property `code` does NOT exist on any node; use `chunk_id`, `line_start`, `line_end`.
4. Add LIMIT 50 to any query that could return many rows.
5. For fuzzy / partial name matching use: WHERE n.name CONTAINS 'keyword'
   OR the full-text index: CALL db.index.fulltext.queryNodes('codeEntityNames','keyword*')
   YIELD node AS n WHERE n.source_id = $source_id RETURN n.name, n.file_path, n.chunk_id

Graph Schema:
{schema}

{reflection_context}

Past Experiences (Episodic Memory):
{episodic_context}

Procedural Instinct:
{procedural_instinct}

User Question: {question}
"""


def _clean_query(raw: str) -> str:
    """Strip any markdown code fences the model might have emitted."""
    q = raw.strip()
    for fence in ("```cypher", "```"):
        if q.startswith(fence):
            q = q[len(fence):]
    if q.endswith("```"):
        q = q[:-3]
    return q.strip()


async def cypher_generator_agent(state: CodeAnalysisState) -> dict:
    logger.info("cypher_generator_started", source_id=state.get("source_id"))

    question        = state.get("question", "")
    schema          = state.get("graph_schema", "")
    reflection      = state.get("reflection_context", "")
    running_summary = state.get("running_summary", "No previous context.")

    reflection_block = (
        f"Previous attempt failed — please fix:\n{reflection}"
        if reflection else ""
    )

    # Simple intent detection for procedural memory (default to dependency)
    intent = "dependency"
    if "implement" in question.lower(): intent = "implementation"
    elif "table" in question.lower() or "datab" in question.lower(): intent = "database"

    procedural_instinct = procedural_memory.get_procedural_knowledge(intent)

    # Retrieve Persistent Episodic Memory
    past_experiences = await episodic_memory.get_related_insights(state.get("tenant_id", "default"), question)
    episodic_context = "No direct past experiences found."
    if past_experiences:
        episodic_context = "\n".join([f"- Previous Question: {e['question']}\n  Successful Cypher: {e['cypher']}" for e in past_experiences])

    prompt = ChatPromptTemplate.from_template(PROMPT)
    llm    = get_llm(temperature=0.1, model=settings.LLM_MODEL_CODE)
    chain  = prompt | llm

    try:
        result = await chain.ainvoke(
            {
                "schema":               schema,
                "question":             question,
                "running_summary":      running_summary,
                "reflection_context":   reflection_block,
                "procedural_instinct":  procedural_instinct,
                "episodic_context":     episodic_context,
            }
        )
        query = _clean_query(result.content)

        return {
            "cypher_query":  query,
            "cypher_params": {"source_id": state.get("source_id")},
            "error":         None,
        }

    except Exception as exc:
        logger.error("cypher_generator_failed", error=str(exc))
        # Do NOT set retry_count here — increment only happens in reflection_agent
        # to keep the counter accurate.
        return {"error": str(exc)}
