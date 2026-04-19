"""
SQL Schema RAG Evaluation Agent — LangGraph Node

Computes Chunk Relevance, Attribution, and Utilization metrics for the retrieved
Data Source Schemas against the user's question and the generated SQL/Insights.
"""
from __future__ import annotations

import json
import structlog
from typing import Any, Dict

from app.domain.analysis.entities import AnalysisState
from app.modules.sql.utils.rag_evaluator import get_evaluator

logger = structlog.get_logger(__name__)


async def evaluation_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Computes RAG quality metrics for the SQL Agent.
    Evaluates how effectively the discovered Schema (schema_summary) 
    was utilized to answer the user's question.
    """
    question = state.get("question", "")
    schema_summary = state.get("schema_summary", {})
    insight_report = state.get("insight_report", "")

    # ── Skip if no data to evaluate ───────────────────────────────────────────
    if not schema_summary or not insight_report:
        logger.info("evaluation_agent_skipped",
                    reason="no schema summary or report")
        return {"evaluation_metrics": None}

    logger.info("evaluation_agent_started",
                question=question[:60])

    try:
        # Convert schema_summary into chunks for the evaluator
        chunks = []
        
        # We can extract the schema tables and their descriptions as "chunks"
        tables = schema_summary.get("tables", [])
        for i, tbl in enumerate(tables):
            name = tbl.get("name", f"table_{i}")
            desc = tbl.get("description", "")
            
            # Format columns
            cols = []
            for c in tbl.get("columns", []):
                cols.append(f"{c.get('name')} ({c.get('type')}): {c.get('description', '')}")
                
            col_str = "\n".join(cols)
            text = f"Table: {name}\nDescription: {desc}\nColumns:\n{col_str}"
            
            chunks.append({
                "chunk_id": name,
                "text": text,
                "element_type": "DatabaseTable"
            })

        # Add Golden SQL entries if present as separate chunks
        golden_sql = schema_summary.get("golden_records", [])
        for i, g in enumerate(golden_sql):
            chunks.append({
                "chunk_id": f"golden_sql_{i}",
                "text": f"Golden Query: {g.get('question', '')}\nSQL: {g.get('sql', '')}",
                "element_type": "GoldenSQL"
            })

        # ── Run evaluation ─────────────────────────────────────────────────────
        if not chunks:
            return {"evaluation_metrics": None}

        evaluator = get_evaluator()
        eval_result = await evaluator.evaluate_retrieval(
            query=question,
            chunks=chunks,
            response=insight_report,
        )

        metrics_dict = eval_result.to_dict()

        logger.info(
            "evaluation_agent_complete",
            attributed=eval_result.attributed_chunks,
            total=eval_result.total_chunks,
            avg_relevance=round(eval_result.avg_relevance, 3),
            avg_utilization=round(eval_result.avg_utilization, 3),
        )

        return {"evaluation_metrics": metrics_dict}

    except Exception as e:
        logger.error("evaluation_agent_failed", error=str(e))
        return {
            "evaluation_metrics": {
                "error": str(e),
                "diagnosis": "Evaluation failed — RAG metrics unavailable.",
            }
        }
