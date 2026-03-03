"""Auto-Analysis Service.

Runs once on first upload/connection per DataSource.
Steps:
  1. Use LLM to inspect schema → detect domain_type + generate 5 smart questions
  2. Run each question through the appropriate pipeline (CSV or SQL)
  3. Save all 5 results to DataSource.auto_analysis_json permanently

Results are cached in the DB — subsequent reads are instant (no re-run).
"""

from __future__ import annotations

import json
import asyncio
import uuid
from typing import Any, Dict, List, Optional

import structlog
from langchain_groq import ChatGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import settings
from app.models.data_source import DataSource

logger = structlog.get_logger(__name__)

# ── Domain Detection + Question Generation Prompt ─────────────────────────────

DISCOVERY_PROMPT = """You are a senior data analyst. Given the following data schema, your job is to:
1. Detect the domain type of this data
2. Generate exactly 5 smart, diverse analysis questions that will give the most business value

Domain types: sales, hr, finance, inventory, customer, logistics, healthcare, education, mixed

Rules for questions:
- Each question should reveal a DIFFERENT insight (trend, ranking, correlation, comparison, summary)
- Questions must be answerable from the given schema
- Questions should be in plain English, as a business user would ask them
- Make them specific (e.g. use actual column names where natural)

Respond ONLY with valid JSON, no markdown:
{{
  "domain_type": "sales",
  "questions": [
    "What is the overall sales trend over time?",
    "Which product category generates the most revenue?",
    "Which region has the highest number of orders?",
    "What is the correlation between discount and profit?",
    "Who are the top 10 customers by total spending?"
  ]
}}

Schema:
{schema}"""


# ── Main Service Function ──────────────────────────────────────────────────────

async def run_auto_analysis(source_id: str, db: AsyncSession) -> None:
    """Run the auto-analysis pipeline for a DataSource.

    This function is called as a FastAPI BackgroundTask immediately after
    a new DataSource is created. It:
    1. Marks the source as 'running'
    2. Generates 5 smart questions via LLM
    3. Runs each question through the pipeline
    4. Saves results back to the DataSource row
    5. Marks as 'done' (or 'failed' on error)
    """
    # Load source
    result = await db.execute(
        select(DataSource).where(DataSource.id == uuid.UUID(source_id))
    )
    source = result.scalar_one_or_none()
    if source is None:
        logger.error("auto_analysis_source_not_found", source_id=source_id)
        return

    logger.info("auto_analysis_started", source_id=source_id, source_type=source.type)

    # Mark as running
    source.auto_analysis_status = "running"
    await db.commit()

    try:
        # Step 1: Generate domain + questions from schema
        schema_str = json.dumps(source.schema_json or {}, indent=2)
        domain_type, questions = await _generate_questions(schema_str)

        source.domain_type = domain_type
        await db.commit()

        # Step 2: Run each question through the pipeline
        results = await _run_questions(source, questions)

        # Step 3: Save results
        source.auto_analysis_json = {
            "domain_type": domain_type,
            "questions": questions,
            "results": results,
        }
        source.auto_analysis_status = "done"
        await db.commit()

        logger.info(
            "auto_analysis_done",
            source_id=source_id,
            domain_type=domain_type,
            questions_run=len(questions),
        )

    except Exception as exc:
        logger.error("auto_analysis_failed", source_id=source_id, error=str(exc))
        source.auto_analysis_status = "failed"
        await db.commit()


# ── Step 1: LLM Question Generator ────────────────────────────────────────────

async def _generate_questions(schema_str: str):
    """Use LLM to detect domain + generate 5 smart questions."""
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=settings.GROCK_API_KEY,
        temperature=0.3,
    )

    prompt = DISCOVERY_PROMPT.format(schema=schema_str)
    response = await llm.ainvoke(prompt)
    content = response.content

    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

    parsed = json.loads(content)
    domain_type = parsed.get("domain_type", "mixed")
    questions = parsed.get("questions", [])[:5]

    return domain_type, questions


# ── Step 2: Run Each Question Through the Pipeline ────────────────────────────

async def _run_questions(
    source: DataSource,
    questions: List[str],
) -> List[Dict[str, Any]]:
    """Run each question through the CSV or SQL pipeline and return results."""
    from app.use_cases.analysis.run_pipeline import get_pipeline

    pipeline = get_pipeline(source.type)
    results = []

    for i, question in enumerate(questions):
        try:
            initial_state = {
                "tenant_id": str(source.tenant_id),
                "user_id": "auto_analysis",
                "question": question,
                "source_id": str(source.id),
                "source_type": source.type,
                "file_path": source.file_path,
                "config_encrypted": source.config_encrypted,
                "schema_summary": source.schema_json or {},
                "retry_count": 0,
            }

            final_state = await pipeline.ainvoke(initial_state)

            results.append({
                "index": i,
                "question": question,
                "status": "done",
                "chart_json": final_state.get("chart_json"),
                "insight_report": final_state.get("insight_report"),
                "executive_summary": final_state.get("executive_summary"),
                "recommendations": final_state.get("recommendations", []),
                "follow_up_suggestions": final_state.get("follow_up_suggestions", []),
                "source_type": source.type,
            })

        except Exception as exc:
            logger.warning(
                "auto_analysis_question_failed",
                question=question,
                error=str(exc),
            )
            results.append({
                "index": i,
                "question": question,
                "status": "failed",
                "error": str(exc),
            })

    return results
