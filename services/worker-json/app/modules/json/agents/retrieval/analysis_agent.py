"""Analysis Agent for JSON — Translates intents to Mongo Pipelines or pandas operations.

Supports: aggregate, forecast, correlation, ranking, trend, groupby, filter, sort, aggregate, pivot.
"""

import json
import logging
from typing import Any, Dict, List

from app.domain.analysis.entities import AnalysisState
from app.infrastructure.llm import get_llm
from app.modules.json.tools.run_mongo_query import run_mongo_query
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)

MONGO_PLAN_PROMPT = """You are a Principal MongoDB Data Engineer.
Your task is to translate the user's question into an operation plan based on the provided schema.

USER QUESTION: {question}

DATASET SCHEMA:
{schema}

OUTPUT FORMAT:
Provide ONLY a valid JSON object. Supported operation types:

1. Normal Aggregation (MongoDB pipeline):
{{
  "operation": "aggregate",
  "pipeline": [
    {{ "$match": {{ "status": "active" }} }},
    {{ "$group": {{ "_id": "$category", "total": {{ "$sum": "$amount" }} }} }}
  ]
}}

2. Forecasting:
{{
  "operation": "forecast",
  "date_column": "timestamp_field_name",
  "value_column": "metric_to_forecast",
  "periods": 30
}}

3. Correlation (which columns are related?):
{{
  "operation": "correlation",
  "columns": ["col1", "col2"],
  "method": "pearson"
}}

4. Ranking / Top-N:
{{
  "operation": "ranking",
  "rank_column": "numeric_col",
  "label_column": "name_col",
  "top_n": 10,
  "sort_order": "desc"
}}

5. Trend over time:
{{
  "operation": "trend",
  "date_column": "date_field",
  "value_column": "metric_field"
}}

6. Generic groupby/filter/sort/aggregate/pivot:
{{
  "operation": "groupby",
  "group_by": ["category"],
  "agg_column": "sales",
  "agg_function": "sum"
}}

CRITICAL RULES:
1. ONLY utilize fields that exist in the DATASET SCHEMA.
2. DO NOT include $out or $merge operations in pipelines.
3. Choose the operation type that best answers the user's question.
"""


async def analysis_agent(state: AnalysisState) -> Dict[str, Any]:
    """Translate question to the right operation and execute it."""
    question = state.get("question")
    schema = state.get("schema_summary", {})
    collection_name = schema.get("collection_name")

    if not question or not collection_name:
        return {"error": "Missing question or schema summary."}

    repaired_plan = state.get("repaired_plan")
    llm = get_llm(temperature=0)

    if repaired_plan:
        plan = repaired_plan
    else:
        history_arr = state.get("history", [])
        chat_history = "No previous conversational context."
        if history_arr:
            chat_history = "\n".join([f"[{msg['role'].upper()}]: {msg['content']}" for msg in history_arr])

        # FAST-TRACK: Check if this is a meta-question (schema, columns, rows)
        meta_result = _handle_meta_question(question, schema)
        if meta_result:
            return {
                "analysis_results": {
                    "plan": {"operation": "meta_bypass", "summary": "Skipped LLM planner for meta-question"},
                    "source_type": "json",
                    "data": meta_result["data"],
                    "columns": list(meta_result["data"][0].keys()) if meta_result["data"] else [],
                    "summary": meta_result["title"]
                },
                "error": None,
                "retry_count": state.get("retry_count", 0),
            }

        prompt = MONGO_PLAN_PROMPT.format(
            question=question,
            schema=json.dumps(schema, indent=2),
            chat_history=chat_history,
        )
        try:
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            plan = json.loads(content)
        except Exception as e:
            logger.error("json_planning_failed", error=str(e))
            return {"error": f"Failed to parse plan: {str(e)}"}

    try:
        operation = plan.get("operation", "aggregate")

        if operation == "forecast":
            from app.modules.json.tools.compute_forecast import compute_json_forecast
            date_col = plan.get("date_column")
            value_col = plan.get("value_column")
            if not date_col or not value_col:
                return {"error": "Forecast requires date_column and value_column.", "analysis_results": {"plan": plan}}
            result = await compute_json_forecast.ainvoke({
                "collection_name": collection_name,
                "date_column": date_col,
                "value_column": value_col,
                "periods": plan.get("periods", 30)
            })

        elif operation == "correlation":
            records = await _fetch_all_records(collection_name)
            from app.modules.json.tools.compute_correlation import compute_correlation
            result = compute_correlation.invoke({
                "records": records,
                "columns": plan.get("columns"),
                "method": plan.get("method", "pearson"),
            })

        elif operation == "ranking":
            records = await _fetch_all_records(collection_name)
            from app.modules.json.tools.compute_ranking import compute_ranking
            result = compute_ranking.invoke({
                "records": records,
                "rank_column": plan.get("rank_column", ""),
                "label_column": plan.get("label_column", ""),
                "top_n": plan.get("top_n", 10),
                "sort_order": plan.get("sort_order", "desc"),
                "date_column": plan.get("date_column"),
            })

        elif operation == "trend":
            records = await _fetch_all_records(collection_name)
            from app.modules.json.tools.compute_trend import compute_trend
            result = compute_trend.invoke({
                "records": records,
                "date_column": plan.get("date_column", ""),
                "value_column": plan.get("value_column", ""),
                "group_by": plan.get("group_by") if isinstance(plan.get("group_by"), str) else None,
            })

        elif operation in ("groupby", "filter", "aggregate", "sort", "pivot"):
            records = await _fetch_all_records(collection_name)
            from app.modules.json.tools.run_pandas_query import run_pandas_query
            group_by = plan.get("group_by")
            if isinstance(group_by, str):
                group_by = [group_by]
            result = run_pandas_query.invoke({
                "records": records,
                "operation": operation,
                "group_by": group_by,
                "agg_column": plan.get("agg_column"),
                "agg_function": plan.get("agg_function", "sum"),
                "sort_by": plan.get("sort_by") or plan.get("agg_column"),
                "sort_order": plan.get("sort_order", "desc"),
                "top_n": plan.get("top_n"),
                "filter_column": plan.get("filter_conditions", [{}])[0].get("column") if plan.get("filter_conditions") else None,
                "filter_value": plan.get("filter_conditions", [{}])[0].get("value") if plan.get("filter_conditions") else None,
            })

        else:
            # Default: MongoDB aggregation pipeline
            pipeline = plan.get("pipeline", [])
            if not pipeline:
                return {"error": "Generated pipeline is empty.", "analysis_results": {"plan": plan}}
            result = await run_mongo_query.ainvoke({
                "collection_name": collection_name,
                "pipeline": pipeline
            })

        if "error" in result:
            return {"error": result["error"], "analysis_results": {"plan": plan}}

        return {
            "analysis_results": {**result, "plan": plan},
            "error": None
        }
    except Exception as e:
        logger.error("json_execution_failed", error=str(e))
        return {"error": f"JSON execution failed: {str(e)}", "analysis_results": {"plan": plan}}


async def _fetch_all_records(collection_name: str, limit: int = 10000) -> List[Dict]:
    """Fetch all documents from a MongoDB collection as a list of dicts (no _id)."""
    from app.infrastructure.mongo_client import MongoDBClient
    db = MongoDBClient.get_db()
    collection = db[collection_name]
    cursor = collection.find({}, {"_id": 0}).limit(limit)
    docs = []
    async for doc in cursor:
        docs.append(doc)
    return docs

def _handle_meta_question(question: str, schema: Dict[str, Any]) -> dict | None:
    """Answer questions ABOUT the dataset structure directly — no LLM needed."""
    q = question.lower().strip()
    columns_info = schema.get("columns", [])
    all_cols = [c["name"] for c in columns_info]
    num_cols = [c["name"] for c in columns_info if "numeric" in c.get("dtype", "").lower() or "int" in c.get("dtype", "").lower() or "float" in c.get("dtype", "").lower()]
    cat_cols = [c["name"] for c in columns_info if "object" in c.get("dtype", "").lower() or "string" in c.get("dtype", "").lower()]
    dt_cols  = [c["name"] for c in columns_info if "datetime" in c.get("dtype", "").lower()]
    n_rows   = schema.get("total_documents", 0)

    # How many columns
    if any(p in q for p in ["how many column", "number of column", "count of column", "how many feature", "how many field", "how many propert", "كم عمود", "كم حقل", "كم خاصية", "عدد الخصائص", "عدد الحقول"]):
        data = [{
            "total_properties": len(all_cols),
            "numeric_properties": len(num_cols),
            "categorical_properties": len(cat_cols),
            "datetime_properties": len(dt_cols),
        }]
        return {"data": data, "title": f"Dataset has {len(all_cols)} properties | البيانات تحتوي على {len(all_cols)} خصائص"}

    # How many rows
    if any(p in q for p in ["how many row", "number of row", "count of row", "how many record", "how many observation", "document count", "how many document", "كم سجل", "كم وثيقة", "عدد السجلات", "حجم البيانات"]):
        data = [{
            "total_documents": n_rows,
            "total_properties": len(all_cols),
        }]
        return {"data": data, "title": f"Collection has {n_rows:,} documents | المجموعة تحتوي على {n_rows:,} وثائق"}

    # Column list / schema
    if any(p in q for p in ["what are the column", "list column", "show column", "what column", "column name", "show schema", "what fields", "what features", "what propert", "describe", "ما هي الاعمدة", "ما هي الأعمدة", "اسماء الحقول", "عرض المخطط"]):
        rows = []
        for c in columns_info:
            rows.append({
                "property": c["name"],
                "type": c.get("dtype", "unknown"),
                "unique_values": c.get("unique_count", 0),
                "missing": c.get("null_count", 0),
            })
        return {"data": rows, "title": f"Schema: {len(all_cols)} properties | مخطط البيانات: {len(all_cols)} حقول"}

    # Missing values
    if any(p in q for p in ["missing", "null", "nan", "empty", "incomplete"]):
        rows = []
        for c in columns_info:
            n_miss = c.get("null_count", 0)
            rows.append({
                "property": c["name"],
                "missing_count": n_miss,
            })
        rows.sort(key=lambda x: x["missing_count"], reverse=True)
        total = sum([r["missing_count"] for r in rows])
        return {"data": rows, "title": f"Missing Data — {total:,} total missing fields"}

    return None
