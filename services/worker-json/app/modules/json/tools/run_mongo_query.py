"""Tool: Execute a MongoDB Aggregation Pipeline safely."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.infrastructure.mongo_client import MongoDBClient

logger = logging.getLogger(__name__)

class MongoQueryInput(BaseModel):
    """Input schema for run_mongo_query tool."""
    collection_name: str = Field(..., description="The name of the MongoDB collection to query.")
    pipeline: List[Dict[str, Any]] = Field(..., description="The MongoDB aggregation pipeline to execute. Supports $match, $group, $sort, $project, $limit.")

@tool("run_mongo_query", args_schema=MongoQueryInput)
async def run_mongo_query(
    collection_name: str,
    pipeline: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Execute a MongoDB aggregation pipeline safely and return the results."""
    try:
        db = MongoDBClient.get_db()
        collection = db[collection_name]
        
        # Enforce safety: no $out or $merge in pipeline to prevent data modification
        for stage in pipeline:
            if "$out" in stage or "$merge" in stage:
                return {"error": "Execution of $out or $merge stages is strictly prohibited for safety."}
        
        # Add a hard limit to prevent OOM
        if not any("$limit" in stage for stage in pipeline):
            pipeline.append({"$limit": 1000})
            
        logger.info("executing_mongo_pipeline", collection=collection_name, pipeline=pipeline)
        
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=1000)
        
        # Convert ObjectId to string if present
        for doc in results:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
                
        return {
            "query": pipeline,
            "data": results,
            "columns": list(results[0].keys()) if results else [],
            "row_count": len(results)
        }
        
    except Exception as e:
        logger.error("mongo_query_failed", error=str(e), pipeline=pipeline)
        return {"error": str(e)}
