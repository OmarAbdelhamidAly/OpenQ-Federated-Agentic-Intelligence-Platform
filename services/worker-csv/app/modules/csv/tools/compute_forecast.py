"""Tool: Compute time-series forecast using Prophet or ARIMA.

CSV Pipeline — supports advanced forecasting and anomaly detection.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ForecastInput(BaseModel):
    """Input schema for compute_forecast tool."""
    file_path: str = Field(..., description="Path to the CSV file")
    date_column: str = Field(..., description="Column with date/time values")
    value_column: str = Field(..., description="Column with numeric values to forecast")
    periods: int = Field(30, description="Number of periods to forecast into the future")
    freq: str = Field("D", description="Frequency of the time series (D, W, M, H)")

@tool("compute_forecast", args_schema=ForecastInput)
def compute_forecast(
    file_path: str,
    date_column: str,
    value_column: str,
    periods: int = 30,
    freq: str = "D",
) -> Dict[str, Any]:
    """Compute time-series forecast using Prophet (primary) or ARIMA (fallback)."""
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return {"error": f"Failed to load CSV: {str(e)}"}

    if date_column not in df.columns or value_column not in df.columns:
        return {"error": f"Columns '{date_column}' or '{value_column}' not found."}

    # Prepare data
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df = df.dropna(subset=[date_column, value_column])
    df = df.sort_values(date_column)
    
    if len(df) < 5:
        return {"error": "Insufficient data points for forecasting (minimum 5 required)."}

    # Resample to the requested frequency to ensure clean intervals
    series = df.set_index(date_column)[value_column].resample(freq).mean().dropna().reset_index()
    series.columns = ['ds', 'y']

    # Downsample if too large for Prophet performance
    if len(series) > 5000:
        series = series.iloc[::max(1, len(series)//2000)]

    try:
        from prophet import Prophet
        
        # Prophet implementation
        m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
        m.fit(series)
        
        future = m.make_future_dataframe(periods=periods, freq=freq)
        forecast = m.predict(future)
        
        # Extract results
        results = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        results['ds'] = results['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Merge actual values back for the historical part
        actuals = series.copy()
        actuals['ds'] = actuals['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
        merged = results.merge(actuals, on='ds', how='left')
        
        return {
            "method": "prophet",
            "forecast": merged.to_dict(orient='records'),
            "periods": periods,
            "freq": freq,
            "metrics": {
                "mean_forecast": float(results['yhat'].tail(periods).mean()),
                "trend": "upward" if results['yhat'].iloc[-1] > results['yhat'].iloc[-periods] else "downward"
            }
        }
        
    except (ImportError, Exception) as e:
        logger.warning("prophet_failed_falling_back_to_arima", error=str(e))
        
        # Fallback to ARIMA (using statsmodels)
        try:
            from statsmodels.tsa.arima.model import ARIMA
            
            model = ARIMA(series['y'], order=(5,1,0))
            model_fit = model.fit()
            
            forecast_values = model_fit.forecast(steps=periods)
            
            # Generate future dates
            last_date = series['ds'].iloc[-1]
            future_dates = pd.date_range(start=last_date, periods=periods+1, freq=freq)[1:]
            
            historical = series.copy()
            historical['ds'] = historical['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
            historical['yhat'] = historical['y']
            
            future_df = pd.DataFrame({
                'ds': future_dates.strftime('%Y-%m-%d %H:%M:%S'),
                'yhat': forecast_values.values,
                'yhat_lower': forecast_values.values * 0.9, # Simple bands for ARIMA fallback
                'yhat_upper': forecast_values.values * 1.1
            })
            
            combined = pd.concat([historical, future_df], ignore_index=True)
            
            return {
                "method": "arima_fallback",
                "forecast": combined.to_dict(orient='records'),
                "periods": periods,
                "freq": freq,
                "warning": "Forecast generated using ARIMA fallback as Prophet was unavailable or failed."
            }
        except Exception as arima_e:
            return {"error": f"Forecasting failed: Prophet and ARIMA both failed. {str(arima_e)}"}
