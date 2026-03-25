"""Tool: Render Plotly chart — figure JSON + PNG export."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Literal, Optional

import plotly.graph_objects as go
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ChartDataTrace(BaseModel):
    """Single data trace for the chart."""
    x: List[Any] = Field(..., description="X-axis values")
    y: Optional[List[Any]] = Field(None, description="Y-axis values")
    labels: Optional[List[str]] = Field(None, description="Labels for pie charts")
    values: Optional[List[float]] = Field(None, description="Values for pie charts")
    name: Optional[str] = Field(None, description="Trace name for legend")


class RenderChartInput(BaseModel):
    """Input schema for render_chart tool."""
    chart_type: Literal["line", "bar", "scatter", "pie", "histogram", "heatmap"] = Field(
        ..., description="Type of chart to render"
    )
    traces: List[ChartDataTrace] = Field(..., description="Data traces for the chart")
    title: str = Field(..., description="Chart title")
    x_label: Optional[str] = Field(None, description="X-axis label")
    y_label: Optional[str] = Field(None, description="Y-axis label")
    output_path: Optional[str] = Field(None, description="Path to save PNG (optional)")


# Professional color palette
COLORS = [
    "#1a73e8", "#ea4335", "#34a853", "#fbbc04",
    "#46bdc6", "#ff6d01", "#9334e6", "#185abc",
]


@tool("render_chart", args_schema=RenderChartInput)
def render_chart(
    chart_type: str,
    traces: List[Dict[str, Any]],
    title: str,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a Plotly chart and return figure JSON + optional PNG.

    Supported chart types: line, bar, scatter, pie, histogram, heatmap.
    """
    fig = go.Figure()

    for i, trace_data in enumerate(traces):
        color = COLORS[i % len(COLORS)]
        x = trace_data.get("x", [])
        y = trace_data.get("y", [])
        name = trace_data.get("name", f"Series {i + 1}")

        if chart_type == "line":
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=name,
                                     line=dict(color=color, width=2)))
        elif chart_type == "bar":
            fig.add_trace(go.Bar(x=x, y=y, name=name, marker_color=color))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(x=x, y=y, mode="markers", name=name,
                                     marker=dict(color=color, size=8)))
        elif chart_type == "pie":
            labels = trace_data.get("labels", x)
            values = trace_data.get("values", y)
            fig.add_trace(go.Pie(labels=labels, values=values,
                                 marker=dict(colors=COLORS)))
        elif chart_type == "histogram":
            fig.add_trace(go.Histogram(x=x, name=name, marker_color=color))
        elif chart_type == "heatmap":
            fig.add_trace(go.Heatmap(z=y, x=x, colorscale="Blues"))

    # Layout
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=80, b=60),
    )

    chart_json = json.loads(fig.to_json())

    # Save PNG if path provided
    png_path = None
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.write_image(output_path, format="png", width=1200, height=800, scale=2)
        png_path = output_path

    return {
        "chart_json": chart_json,
        "png_path": png_path,
    }
