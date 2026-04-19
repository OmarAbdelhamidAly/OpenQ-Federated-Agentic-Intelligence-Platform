import os
import json
import structlog
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.infrastructure.config import settings
from app.domain.analysis.entities import CodeAnalysisState
from app.infrastructure.code_store import CodeStore

logger = structlog.get_logger(__name__)

PROMPT = """\
You are a Principal Software Engineer explaining codebase analysis results to a fellow developer.

Previous Conversation Context:
{running_summary}

User Question:
{question}

Neo4j Query Results (structural data):
{results}

Relevant Code Snippets (loaded on-demand):
{snippets}

Write a clear, technical insight report that:
  - Directly answers the user's question.
  - References specific file paths, function names, and line numbers from the results.
  - Quotes relevant code snippets where helpful (do not fabricate code).
  - Is concise — avoid padding or generic filler sentences.

Output plain text only. No markdown headers, no JSON, no ``` fences.
"""


async def insight_agent(state: CodeAnalysisState) -> dict:
    """
    Generate a human-readable insight report from Neo4j results.

    Code loading strategy
    ---------------------
    Execution results may contain `chunk_id` references.  We load those
    snippets on-demand from CodeStore (filesystem) and inject them into
    the LLM prompt.  This keeps Neo4j properties lean while still giving
    the model access to actual source code when building its explanation.

    We load at most 3 snippets and cap total snippet content to ~3 000
    characters to stay comfortably inside the LLM context window.
    """
    source_id       = state.get("source_id", "")
    question        = state.get("question", "")
    results         = state.get("execution_results", [])
    running_summary = state.get("running_summary", "No previous context.")

    logger.info("insight_agent_started", source_id=source_id, result_count=len(results))

    # ── Serialise results (cap to 4 000 chars for safety) ─────────────
    results_str = json.dumps(results, indent=2)[:4000]

    # ── Load code snippets referenced in results ──────────────────────
    store      = CodeStore()
    chunk_ids  = [
        r["chunk_id"]
        for r in results
        if isinstance(r, dict) and "chunk_id" in r
    ][:3]  # cap to 3 snippets

    snippets_data = store.load_many(source_id, chunk_ids, max_chars=3000)

    if snippets_data:
        snippets_str = "\n\n".join(
            f"--- {s['chunk_id']} ---\n{s['code']}" for s in snippets_data
        )
    else:
        snippets_str = "(no code snippets available for these results)"

    # ── Call LLM ──────────────────────────────────────────────────────
    prompt = ChatPromptTemplate.from_template(PROMPT)
    llm    = get_llm(temperature=0.3, model=settings.LLM_MODEL_CODE)
    chain  = prompt | llm

    try:
        response = await chain.ainvoke({
            "question": question,
            "results": results_str,
            "snippets": snippets_str,
            "running_summary": running_summary
        })

        return {
            "insight_report":    response.content.strip(),
            "executive_summary": "Codebase analysis completed successfully.",
            "code_snippets":     snippets_data,
            "error":             None,
        }

    except Exception as exc:
        logger.error("insight_agent_failed", error=str(exc))
        return {
            "insight_report":    f"Analysis complete but summary generation failed: {exc}",
            "executive_summary": "See insight report for details.",
            "error":             None,   # non-fatal — we still have raw results
        }
