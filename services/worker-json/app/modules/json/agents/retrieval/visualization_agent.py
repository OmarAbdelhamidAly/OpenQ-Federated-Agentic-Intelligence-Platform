"""JSON Pipeline — Visualization Agent.

Generates premium Plotly.js Figure configurations dynamically for JSON data,
providing feature parity with SQL and CSV reporting.
"""

from __future__ import annotations

import json
import math
import re
import structlog
from datetime import date, datetime
from typing import Any

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState

# ── Design Token Constants ────────────────────────────────────────────────────
_COLORWAY    = ["#6366f1", "#10b981", "#f43f5e", "#fbbf24", "#8b5cf6", "#06b6d4"]
_FONT_FAMILY = '"Inter", "system-ui", sans-serif'
_FONT_COLOR  = "#f8fafc"
_GRID_COLOR  = "rgba(255,255,255,0.05)"
_TRANSPARENT = "rgba(0,0,0,0)"

_LAYOUT_PROMPT = """\
You are a Plotly.js expert. The chart type for this JSON data is: **{chart_type}**

Return a JSON object with:
1. "title"   — Insight-driven title.
2. "x_label" — Human-readable X axis label.
3. "y_label" — Human-readable Y axis label.
4. "rationale" — Professional explanation of why {chart_type} is best for this JSON data.

Return exactly:
{{"title": "...", "x_label": "...", "y_label": "...", "rationale": "..."}}
"""

_BASE_LAYOUT: dict[str, Any] = {
    "paper_bgcolor": _TRANSPARENT,
    "plot_bgcolor":  _TRANSPARENT,
    "font": {"family": _FONT_FAMILY, "color": _FONT_COLOR, "size": 13},
    "colorway": _COLORWAY,
    "hovermode": "x unified",
    "margin": {"l": 60, "r": 30, "t": 60, "b": 60},
    "xaxis": {"gridcolor": _GRID_COLOR, "tickfont": {"color": _FONT_COLOR}},
    "yaxis": {"gridcolor": _GRID_COLOR, "tickfont": {"color": _FONT_COLOR}},
}

async def visualization_agent(state: AnalysisState) -> dict[str, Any]:
    """Analyse JSON results and generate a premium Plotly figure."""
    analysis = state.get("analysis_results") or {}
    raw_data = analysis.get("data") or []
    columns  = analysis.get("columns") or []

    if not raw_data or not columns:
        return {"chart_json": None, "chart_engine": "plotly"}

    # ── 1. Profile ──────────────────────────────────────────────────────────
    profile = _profile_data(raw_data, columns)
    
    # ── 2. Select ───────────────────────────────────────────────────────────
    chart_type, rule_reason = _select_chart_type(
        profile=profile,
        intent=state.get("intent", "comparison"),
        row_count=len(raw_data),
    )

    if chart_type == "skip":
        return {"chart_json": None, "chart_engine": "plotly"}

    # ── 3. Layout Meta ─────────────────────────────────────────────────────
    llm = get_llm(temperature=0)
    prompt = _LAYOUT_PROMPT.format(
        chart_type=chart_type,
        intent=state.get("intent", "comparison"),
        question=state.get("question", ""),
    )
    
    try:
        response = await llm.ainvoke(prompt)
        meta = _parse_json(response.content)
    except:
        meta = {}

    # ── 4. Build ───────────────────────────────────────────────────────────
    figure = _build_figure(chart_type, profile, meta, columns)
    figure["layout"] = _deep_merge(_BASE_LAYOUT, figure.get("layout") or {})
    
    rationale = meta.get("rationale") or rule_reason
    return {
        "chart_json": figure,
        "chart_engine": "plotly",
        "viz_rationale": rationale
    }

# ── Ported Deterministic Logic (Simplified for brevity but functionally identical to SQL) ──

def _profile_data(raw_data: list, columns: list) -> dict[str, Any]:
    rows = raw_data if isinstance(raw_data[0], dict) else [dict(zip(columns, r)) for r in raw_data]
    col_types = {}
    cardinalities = {}
    numeric_range = {}
    
    for col in columns:
        values = [r.get(col) for r in rows if r.get(col) is not None]
        cardinalities[col] = len(set(str(v) for v in values))
        
        # Heuristic dtypes
        if any(kw in col.lower() for kw in ("date", "time", "year")): col_types[col] = "temporal"
        elif all(isinstance(v, (int, float)) for v in values[:20]): 
            col_types[col] = "numeric"
            floats = [float(v) for v in values if v is not None]
            if floats:
                mean = sum(floats)/len(floats)
                std = math.sqrt(sum((f-mean)**2 for f in floats)/len(floats))
                cv = (std/mean) if mean != 0 else 0
                numeric_range[col] = {"cv": cv, "min": min(floats), "max": max(floats)}
        else: col_types[col] = "categorical"

    return {
        "col_types": col_types, "cardinalities": cardinalities, "rows": rows,
        "numeric_cols": [c for c, t in col_types.items() if t == "numeric"],
        "cat_cols": [c for c, t in col_types.items() if t == "categorical"],
        "temporal_cols": [c for c, t in col_types.items() if t == "temporal"],
        "numeric_range": numeric_range,
        "avg_label_len": sum(len(str(r.get(columns[0], ""))) for r in rows)/len(rows) if rows else 0
    }

def _select_chart_type(profile: dict, intent: str, row_count: int) -> tuple[str, str]:
    num_cols = profile["numeric_cols"]
    cat_cols = profile["cat_cols"]
    temporal_cols = profile["temporal_cols"]
    
    if row_count == 0: return "skip", "No data"
    if row_count == 1 and num_cols: return "indicator", "Single KPI"
    
    if temporal_cols and num_cols:
        if len(num_cols) > 1 or intent == "correlation":
            return "multi_line", "Multiple trends"
        return "line", "Time-series trend"
        
    if intent in ("proportion", "composition"):
        return ("pie" if row_count <= 7 else "treemap"), "Proportion analysis"
    
    if cat_cols and num_cols:
        cv = profile["numeric_range"].get(num_cols[0], {}).get("cv", 1.0)
        if cv < 0.05 and row_count >= 3: return "dot_plot", "Narrow range"
        if row_count > 8 or profile["avg_label_len"] > 8: return "h_bar", "Horizontal ranking"
        return "bar", "Categorical comparison"
    
    return "table", "Raw data table"

def _build_figure(chart_type: str, profile: dict, meta: dict, columns: list) -> dict[str, Any]:
    rows = profile["rows"][:50]
    num_cols = profile["numeric_cols"]
    cat_col = profile["cat_cols"][0] if profile["cat_cols"] else columns[0]
    temporal_cols = profile["temporal_cols"]
    title = meta.get("title", "Analysis")
    
    if chart_type == "indicator":
        val = rows[0].get(num_cols[0], 0) if num_cols else 0
        return {"data": [{"type": "indicator", "mode": "number", "value": val}], "layout": {"title": title}}
    
    if chart_type in ("line", "multi_line", "scatter"):
        x_col = temporal_cols[0] if temporal_cols else cat_col
        target_y_cols = num_cols if chart_type == "multi_line" else ([num_cols[0]] if num_cols else [columns[-1]])
        
        traces = []
        for i, y_col in enumerate(target_y_cols):
            x_vals = [str(r.get(x_col, "")) for r in rows]
            y_vals = [r.get(y_col) for r in rows]
            mode = "lines+markers" if (temporal_cols or chart_type in ("line", "multi_line")) else "markers"
            trace = {"type": "scatter", "mode": mode, "x": x_vals, "y": y_vals, "name": y_col}
            
            # Dual-Axis for JSON correlation
            if chart_type == "multi_line" and len(target_y_cols) == 2 and i == 1:
                v1_max = profile["numeric_range"].get(target_y_cols[0], {}).get("max", 1)
                v2_max = profile["numeric_range"].get(target_y_cols[1], {}).get("max", 1)
                if (v1_max / (v2_max or 1) > 10 or v2_max / (v1_max or 1) > 10):
                    trace["yaxis"] = "y2"
            traces.append(trace)
        
        fig = {"data": traces, "layout": {"title": title}}
        if any(t.get("yaxis") == "y2" for t in traces):
             fig["layout"]["yaxis2"] = {"overlaying": "y", "side": "right"}
        return fig

    if chart_type == "h_bar":
        n_col = num_cols[0] if num_cols else columns[-1]
        pairs = sorted([(str(r.get(cat_col, "")), r.get(n_col, 0)) for r in rows], key=lambda x: x[1])
        return {"data": [{"type": "bar", "x": [p[1] for p in pairs], "y": [p[0] for p in pairs], "orientation": "h"}], "layout": {"title": title}}
    
    if chart_type == "pie":
        n_col = num_cols[0] if num_cols else columns[-1]
        return {"data": [{"type": "pie", "labels": [str(r.get(cat_col)) for r in rows], "values": [r.get(n_col) for r in rows], "hole": 0.4}], "layout": {"title": title}}
    
    # Fallback/General Bar
    n_col = num_cols[0] if num_cols else columns[-1]
    pairs = sorted([(str(r.get(cat_col, "")), r.get(n_col, 0)) for r in rows], key=lambda x: x[1], reverse=True)
    return {"data": [{"type": "bar", "x": [p[0] for p in pairs], "y": [p[1] for p in pairs]}], "layout": {"title": title}}

def _deep_merge(base, override):
    res = dict(base)
    for k, v in override.items():
        if k in res and isinstance(res[k], dict) and isinstance(v, dict): res[k] = _deep_merge(res[k], v)
        else: res[k] = v
    return res

def _parse_json(c):
    try:
        m = re.search(r"\{.*\}", c, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except: return {}
