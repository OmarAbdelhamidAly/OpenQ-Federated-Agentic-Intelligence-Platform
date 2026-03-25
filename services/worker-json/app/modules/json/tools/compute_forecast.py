"""JSON Tool: Compute time-series forecast using Prophet after Mongo aggregation."""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.infrastructure.mongo_client import MongoDBClient

logger = logging.getLogger(__name__)

class JsonForecastInput(BaseModel):
    """Input schema for JSON compute_forecast tool."""
    collection_name: str = Field(..., description="The name of the MongoDB collection.")
    date_column: str = Field(..., description="Field with date/time values.")
    value_column: str = Field(..., description="Numeric field to forecast.")
    periods: int = Field(30, description="Number of periods to forecast.")
    freq: str = Field("D", description="Frequency of the time series (D, W, M).")

@tool("compute_json_forecast", args_schema=JsonForecastInput)
async def compute_json_forecast(
    collection_name: str,
    date_column: str,
    value_column: str,
    periods: int = 30,
    freq: str = "D",
) -> Dict[str, Any]:
    """Aggregate time-series from MongoDB and compute forecast using Prophet."""
    try:
        db = MongoDBClient.get_db()
        collection = db[collection_name]
        
        # Build aggregation to get daily/weekly/monthly sums/averages
        # Note: In a production scenario, $dateTrunc or $dateToString handles aggregation.
        # For simplicity, we just pull the required fields and aggregate via pandas.
        pipeline = [
            {"$match": {date_column: {"$exists": True, "$ne": None}, value_column: {"$exists": True, "$ne": None}}},
            {"$project": {"ds": f"${date_column}", "y": f"${value_column}", "_id": 0}},
            {"$limit": 50000} # Protect memory
        ]
        
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=50000)
        
        if len(results) < 5:
            return {"error": "Insufficient data points for forecasting."}
            
        df = pd.DataFrame(results)
        df['ds'] = pd.to_datetime(df['ds'], errors='coerce')
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna(subset=['ds', 'y'])
        
        if len(df) < 5:
            return {"error": "Insufficient valid numerical/date data points."}
            
        # Resample
        series = df.set_index('ds')['y'].resample(freq).mean().dropna().reset_index()
        series.columns = ['ds', 'y']
        
        from prophet import Prophet
        
        m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
        m.fit(series)
        
        future = m.make_future_dataframe(periods=periods, freq=freq)
        forecast = m.predict(future)
        
        results_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        results_df['ds'] = results_df['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        actuals = series.copy()
        actuals['ds'] = actuals['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
        merged = results_df.merge(actuals, on='ds', how='left')
        
        return {
            "method": "prophet",
            "forecast": merged.to_dict(orient='records'),
            "periods": periods,
            "freq": freq,
            "query": pipeline, # Just to show what was pulled
            "data": merged.to_dict(orient='records') # duplicate for common interface
        }
        
    except Exception as e:
        logger.error("json_prophet_failed", error=str(e))
        return {"error": f"Forecasting failed: {str(e)}"}
