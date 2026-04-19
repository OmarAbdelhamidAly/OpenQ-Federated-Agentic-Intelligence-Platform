"""SQL Pipeline — Visualization Agent.

Generates premium Plotly.js Figure configurations dynamically via LLM,
with deterministic pre-analysis, strict validation, and robust hydration.

Decision flow:
    1. _profile_data()        → derive cardinality, dtypes, shape
    2. _select_chart_type()   → deterministic rule-engine (no LLM guessing)
    3. LLM call               → only generates layout + aesthetic config
    4. _validate_figure()     → hard reject bad traces before merge
    5. _hydrate_traces()      → replace stubs with full data
    6. _merge_layout()        → inject dark-mode tokens

FIX LOG (v2):
    - [FIX-1] Pie/Donut: تشتغل على proportion intent بغض النظر عن row_count
    - [FIX-2] Treemap: تتفعل لما categories > 7 في proportion context
                       + لما cardinality > 10 في categorical comparison
    - [FIX-3] Horizontal Bar: تتفعل لما labels طويلة (avg > 8 chars) أو categories > 8
    - [FIX-4] Dot Plot: تتفعل لما range ضيق (coefficient of variation < 0.05)
    - [FIX-5] Title bug: الـ LLM prompt بيتبعت مع السؤال الصح دايماً (كان موجود في state)
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

# ── Chart-type registry ───────────────────────────────────────────────────────
_CHART_RULES: list[tuple[str, str]] = [
    ("indicator",  "Single numeric KPI — number indicator is clearest"),
    ("line",       "Time-series or date x-axis — line chart shows trend"),
    ("multi_line", "Multiple metrics over time — dual-axis or multi-trace line chart"),
    ("pie",        "Part-to-whole with 2–7 categories — donut shows proportion"),
    ("treemap",    "Part-to-whole with 8+ categories — treemap avoids label clutter"),
    ("dot_plot",   "Narrow numeric range — dot plot avoids exaggerating differences"),
    ("h_bar",      "Long category labels or many categories — horizontal bar"),
    ("bar",        "Categorical comparison — bar chart ranks discrete groups"),
    ("histogram",  "Single numeric column distribution"),
    ("scatter",    "Two numeric columns — scatter shows correlation"),
    ("table",      "Fallback: no better visual encoding available"),
]

# ── LLM Prompt (layout-only; chart type is pre-decided) ───────────────────────
_LAYOUT_PROMPT = """\
You are a Plotly.js visualization expert working on a dark-mode analytics dashboard.

The chart type has already been decided: **{chart_type}**
Do NOT change it.

Your only job is to return a JSON object with:
1. "title"   — A high-impact, business-focused title (e.g., "Market Dominance" instead of "Sales by Category").
2. "x_label" — A clean, human-readable label for the X axis.
3. "y_label" — A clean, human-readable label for the Y axis.
4. "rationale" — A professional, consultant-grade explanation of why this chart type is optimal for this data.

Rules:
- Return ONLY valid JSON. No markdown. No preamble.
- "title" must describe the insight, not repeat the question.
- The title MUST reflect the actual question being answered. Do not reuse titles from previous questions.

Context:
  Intent      : {intent}
  Question    : {question}
  Chart type  : {chart_type}
  Columns     : {columns}
  Row count   : {row_count}
  Data sample : {data_sample}

Return exactly:
{{"title": "...", "x_label": "...", "y_label": "...", "rationale": "..."}}
"""

# ── Premium Dark-Mode Layout ──────────────────────────────────────────────────
_BASE_LAYOUT: dict[str, Any] = {
    "paper_bgcolor": _TRANSPARENT,
    "plot_bgcolor":  _TRANSPARENT,
    "font": {"family": _FONT_FAMILY, "color": _FONT_COLOR, "size": 13},
    "colorway": _COLORWAY,
    "hovermode": "x unified",
    "hoverlabel": {
        "bgcolor":     "rgba(15,15,30,0.9)",
        "bordercolor": "rgba(255,255,255,0.15)",
        "font": {"family": _FONT_FAMILY, "color": _FONT_COLOR, "size": 12},
    },
    "legend": {
        "bgcolor":     "rgba(255,255,255,0.04)",
        "bordercolor": "rgba(255,255,255,0.08)",
        "borderwidth": 1,
        "font": {"color": _FONT_COLOR},
    },
    "margin": {"l": 60, "r": 30, "t": 60, "b": 60},
    "xaxis": {
        "gridcolor":    _GRID_COLOR,
        "linecolor":    "rgba(255,255,255,0.1)",
        "tickfont":     {"color": _FONT_COLOR},
        "title":        {"font": {"color": _FONT_COLOR}},
        "zerolinecolor":"rgba(255,255,255,0.08)",
    },
    "yaxis": {
        "gridcolor":    _GRID_COLOR,
        "linecolor":    "rgba(255,255,255,0.1)",
        "tickfont":     {"color": _FONT_COLOR},
        "title":        {"font": {"color": _FONT_COLOR}},
        "zerolinecolor":"rgba(255,255,255,0.08)",
    },
    "title": {
        "font": {"family": _FONT_FAMILY, "color": _FONT_COLOR, "size": 18},
        "x": 0.04,
        "xanchor": "left",
    },
}

_RESPONSIVE_CONFIG: dict[str, Any] = {"responsive": True, "displayModeBar": False}


# ═════════════════════════════════════════════════════════════════════════════
# Public agent entry-point
# ═════════════════════════════════════════════════════════════════════════════

async def visualization_agent(state: AnalysisState) -> dict[str, Any]:
    """
    Analyse SQL results, decide chart type deterministically, then call
    LLM only for layout labels. Returns a fully-hydrated Plotly figure.
    """
    analysis = state.get("analysis_results") or {}
    raw_data: list = analysis.get("data") or []
    columns:  list = analysis.get("columns") or []

    if not raw_data or not columns:
        logger.warning("visualization_no_data", state_keys=list(state.keys()))
        return _no_chart("No data available for visualization")

    # ── 1. Profile the data ───────────────────────────────────────────────────
    profile = _profile_data(raw_data, columns)
    logger.info("data_profile", job_id=state.get("job_id"), **{
        k: v for k, v in profile.items() if k != "rows"
    })

    # ── 2. Decide chart type deterministically ────────────────────────────────
    chart_type, rule_reason = _select_chart_type(
        profile=profile,
        intent=state.get("intent", "comparison"),
        row_count=len(raw_data),
    )

    # ── 3. Skip visualization for trivial data ────────────────────────────────
    if chart_type == "skip":
        logger.info("visualization_skipped", reason=rule_reason, job_id=state.get("job_id"))
        return _no_chart(None)

    # ── 4. Ask LLM only for labels / title ───────────────────────────────────
    # [FIX-5] بنبعت السؤال الصح دايماً من state مباشرة
    layout_meta = await _fetch_layout_meta(
        chart_type=chart_type,
        intent=state.get("intent", "comparison"),
        question=_sanitize_question(state.get("question", "")),
        columns=columns,
        row_count=len(raw_data),
        data_sample=raw_data[:10],
    )

    # ── 5. Build figure from deterministic chart type + full data ─────────────
    figure = _build_figure(
        chart_type=chart_type,
        raw_data=raw_data[:50],
        columns=columns,
        profile=profile,
        layout_meta=layout_meta,
    )

    # ── 6. Validate figure before sending ────────────────────────────────────
    validation_error = _validate_figure(figure)
    if validation_error:
        logger.warning(
            "figure_validation_failed",
            reason=validation_error,
            job_id=state.get("job_id"),
        )
        figure = _build_fallback_table(analysis)

    # ── 7. Merge dark-mode layout ─────────────────────────────────────────────
    figure["layout"] = _deep_merge(_BASE_LAYOUT, figure.get("layout") or {})
    figure["config"] = _RESPONSIVE_CONFIG

    rationale = layout_meta.get("rationale") or rule_reason
    logger.info(
        "plotly_figure_built",
        job_id=state.get("job_id"),
        chart_type=chart_type,
        trace_count=len(figure["data"]),
        rationale=rationale,
    )
    return {"chart_json": figure, "chart_engine": "plotly", "viz_rationale": rationale}


# ═════════════════════════════════════════════════════════════════════════════
# Step 1 — Data Profiling
# ═════════════════════════════════════════════════════════════════════════════

def _profile_data(raw_data: list, columns: list) -> dict[str, Any]:
    """
    Derive column-level statistics needed for deterministic chart selection.

    Returns:
        col_types      : {col_name: "numeric" | "temporal" | "categorical"}
        cardinalities  : {col_name: int}
        numeric_cols   : [col_name, ...]
        temporal_cols  : [col_name, ...]
        cat_cols       : [col_name, ...]
        n_cols         : int
        n_rows         : int
        numeric_range  : {col_name: {"min": float, "max": float, "cv": float}}
        avg_label_len  : float   — avg char length of categorical values
    """
    rows: list[dict] = _normalise_rows(raw_data, columns)

    col_types: dict[str, str]     = {}
    cardinalities: dict[str, int] = {}
    # [FIX-3, FIX-4] إضافة range stats و label length
    numeric_range: dict[str, dict] = {}

    for col in columns:
        values = [r.get(col) for r in rows if r.get(col) is not None]
        unique_vals = set(str(v) for v in values)
        cardinalities[col] = len(unique_vals)

        if _is_temporal_col(col, values):
            col_types[col] = "temporal"
        elif _is_numeric_col(values):
            col_types[col] = "numeric"
            # [FIX-4] احسب range statistics للـ numeric columns
            floats = [_coerce_float(v) for v in values]
            floats = [f for f in floats if f is not None]
            if floats:
                mn, mx = min(floats), max(floats)
                mean   = sum(floats) / len(floats)
                # Coefficient of Variation = std/mean — لو صغير → range ضيق
                variance = sum((f - mean) ** 2 for f in floats) / len(floats)
                std      = math.sqrt(variance)
                cv       = (std / mean) if mean != 0 else 0
                numeric_range[col] = {"min": mn, "max": mx, "cv": cv, "mean": mean}
        else:
            col_types[col] = "categorical"

    numeric_cols  = [c for c, t in col_types.items() if t == "numeric"]
    temporal_cols = [c for c, t in col_types.items() if t == "temporal"]
    cat_cols      = [c for c, t in col_types.items() if t == "categorical"]

    # [FIX-3] احسب متوسط طول الـ labels للـ categorical columns
    avg_label_len = 0.0
    if cat_cols:
        all_labels = []
        for col in cat_cols:
            all_labels.extend(str(r.get(col, "")) for r in rows if r.get(col) is not None)
        avg_label_len = sum(len(l) for l in all_labels) / len(all_labels) if all_labels else 0.0

    return {
        "col_types":     col_types,
        "cardinalities": cardinalities,
        "numeric_cols":  numeric_cols,
        "temporal_cols": temporal_cols,
        "cat_cols":      cat_cols,
        "n_cols":        len(columns),
        "n_rows":        len(rows),
        "rows":          rows,
        "numeric_range": numeric_range,       # [FIX-4]
        "avg_label_len": avg_label_len,       # [FIX-3]
    }


def _normalise_rows(raw_data: list, columns: list) -> list[dict]:
    if not raw_data:
        return []
    if isinstance(raw_data[0], dict):
        return raw_data
    return [
        {columns[i]: row[i] for i in range(min(len(columns), len(row)))}
        for row in raw_data
    ]


def _is_numeric_col(values: list) -> bool:
    if not values:
        return False
    numeric_count = sum(1 for v in values if _coerce_float(v) is not None)
    return numeric_count / len(values) >= 0.85


def _is_temporal_col(col_name: str, values: list) -> bool:
    temporal_keywords = ("date", "time", "year", "month", "day", "week", "period", "ts", "at")
    if any(kw in col_name.lower() for kw in temporal_keywords):
        return True
    if not values:
        return False
    sample  = values[:10]
    parsed  = sum(1 for v in sample if _coerce_datetime(v) is not None)
    return parsed / len(sample) >= 0.7


def _coerce_float(v: Any) -> float | None:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _coerce_datetime(v: Any) -> datetime | None:
    if isinstance(v, (datetime, date)):
        return v if isinstance(v, datetime) else datetime(v.year, v.month, v.day)
    if not isinstance(v, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(v[:19], fmt)
        except ValueError:
            continue
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Step 2 — Deterministic Chart Selection  (الجزء الرئيسي للـ Fix)
# ═════════════════════════════════════════════════════════════════════════════

def _select_chart_type(
    profile: dict[str, Any],
    intent: str,
    row_count: int,
) -> tuple[str, str]:
    """
    Rule-engine that selects chart type from data shape — NOT from LLM.

    Priority order (من الأكثر specificity للأقل):
      1. Guard: no data / single KPI
      2. KPI intent override
      3. Time-series
      4. Distribution
      5. Proportion/Composition  → pie (≤7) or treemap (>7)   [FIX-1, FIX-2]
      6. Narrow numeric range    → dot_plot                    [FIX-4]
      7. Categorical comparison  → h_bar or bar                [FIX-2, FIX-3]
      8. Two numeric             → scatter
      9. Fallback                → table
    """
    n_cols        = profile["n_cols"]
    numeric_cols  = profile["numeric_cols"]
    temporal_cols = profile["temporal_cols"]
    cat_cols      = profile["cat_cols"]
    cardinalities = profile["cardinalities"]
    numeric_range = profile.get("numeric_range", {})
    avg_label_len = profile.get("avg_label_len", 0.0)

    # ── Guard: trivially small data ──────────────────────────────────────────
    if row_count == 0:
        return "skip", "No rows to visualise"

    if row_count == 1 and len(numeric_cols) == 1:
        return "indicator", "Single numeric result — KPI indicator"

    # ── KPI intent override ───────────────────────────────────────────────────
    if intent == "kpi" and len(numeric_cols) >= 1 and row_count == 1:
        return "indicator", "Strategic KPI — Single-metric focus"

    # ── Time-series ───────────────────────────────────────────────────────────
    if temporal_cols and numeric_cols:
        if len(numeric_cols) > 1 or intent == "correlation":
            return "multi_line", f"Multiple trends via '{temporal_cols[0]}'"
        return "line", (
            f"Temporal column '{temporal_cols[0]}' + numeric '{numeric_cols[0]}' → line chart"
        )

    # ── Distribution ─────────────────────────────────────────────────────────
    if intent == "distribution" and len(numeric_cols) == 1 and n_cols == 1:
        return "histogram", f"Distribution of '{numeric_cols[0]}'"

    # ── [FIX-1 + FIX-2] Part-to-whole / Proportions ──────────────────────────
    # المشكلة القديمة: الـ rule كانت بتحتاج row_count <= 7 حتى بدون proportion intent
    # الـ Fix: لو intent == proportion → مباشرة pie أو treemap بناءً على cardinality بس
    if intent in ("proportion", "composition"):
        cat_col  = cat_cols[0] if cat_cols else None
        n_unique = cardinalities.get(cat_col, row_count) if cat_col else row_count
        if n_unique <= 7:
            return "pie", f"Proportion intent + {n_unique} categories → donut chart"
        else:
            return "treemap", f"Proportion intent + {n_unique} categories → treemap (avoids label clutter)"

    # تاني حالة proportion: 1 cat + 1 numeric و row_count صغير (بدون explicit intent)
    if len(cat_cols) == 1 and len(numeric_cols) == 1 and 2 <= row_count <= 7:
        cat_col  = cat_cols[0]
        n_unique = cardinalities.get(cat_col, row_count)
        if n_unique <= 7:
            return "pie", f"Small group ({n_unique} categories) + single metric → donut"

    # ── [FIX-4] Dot Plot: narrow numeric range ────────────────────────────────
    # لو عندنا categorical + numeric وكل الـ numeric values متقاربة جداً
    # نستخدم dot plot عشان bar chart بيكذب بصرياً على الفرق
    if cat_cols and numeric_cols:
        num_col   = numeric_cols[0]
        rng_stats = numeric_range.get(num_col, {})
        cv        = rng_stats.get("cv", 1.0)  # Coefficient of Variation

        # CV < 0.05 means values are within ~5% of each other → range ضيق
        if cv < 0.05 and row_count >= 3:
            return "dot_plot", (
                f"Narrow value range (CV={cv:.3f}) for '{num_col}' → "
                f"dot plot avoids visually exaggerating {rng_stats.get('min', 0):.2f}–"
                f"{rng_stats.get('max', 0):.2f} spread"
            )

    # ── [FIX-3] Categorical comparison → h_bar or bar ────────────────────────
    if cat_cols and numeric_cols:
        cat_col  = cat_cols[0]
        n_unique = cardinalities.get(cat_col, row_count)

        if n_unique > 30:
            return "table", f"Too many categories ({n_unique}) for bar — using table"

        # [FIX-2] لو categories > 10 وفي proportion context → treemap
        # (حتى لو intent مش proportion explicitly)
        if n_unique > 10 and intent in ("proportion", "composition", "ranking"):
            return "treemap", (
                f"High cardinality ({n_unique} categories) in ranking/proportion context → treemap"
            )

        # [FIX-3] الـ horizontal bar decision:
        # - لو avg label length > 8 chars → h_bar (عشان الـ labels مش تتداخل)
        # - أو لو n_unique > 8 → h_bar (أسهل للقراءة)
        use_horizontal = avg_label_len > 8 or n_unique > 8
        if use_horizontal:
            return "h_bar", (
                f"{'Long labels (avg {avg_label_len:.1f} chars)' if avg_label_len > 8 else ''}"
                f"{'Many categories (' + str(n_unique) + ')' if n_unique > 8 else ''}"
                f" → horizontal bar for readability"
            )

        return "bar", (
            f"Categorical comparison: '{cat_col}' vs '{numeric_cols[0]}' ({n_unique} categories)"
        )

    # ── Two numeric columns → scatter / correlation ───────────────────────────
    if len(numeric_cols) >= 2:
        return "scatter", f"Correlation between '{numeric_cols[0]}' and '{numeric_cols[1]}'"

    # ── Single numeric column ─────────────────────────────────────────────────
    if len(numeric_cols) == 1 and row_count == 1:
        return "indicator", f"Single numeric value: '{numeric_cols[0]}'"

    # ── Fallback ──────────────────────────────────────────────────────────────
    return "table", "No clear visual encoding — raw table"


# ═════════════════════════════════════════════════════════════════════════════
# Step 3 — LLM: labels only
# ═════════════════════════════════════════════════════════════════════════════

async def _fetch_layout_meta(
    chart_type: str,
    intent: str,
    question: str,
    columns: list,
    row_count: int,
    data_sample: list,
) -> dict[str, str]:
    """Ask LLM only for title, axis labels, and rationale. Never chart type."""
    llm    = get_llm(temperature=0)
    prompt = _LAYOUT_PROMPT.format(
        chart_type=chart_type,
        intent=intent,
        question=question,
        columns=json.dumps(columns),
        row_count=row_count,
        data_sample=json.dumps(data_sample[:10], indent=2, default=str),
    )
    try:
        response = await llm.ainvoke(prompt)
        meta     = _parse_json(response.content)
        return {
            "title":     meta.get("title")    or question[:80],
            "x_label":   meta.get("x_label")  or "",
            "y_label":   meta.get("y_label")   or "",
            "rationale": meta.get("rationale") or f"{chart_type} chart selected for this data.",
        }
    except Exception as exc:
        logger.warning("layout_meta_llm_failed", error=str(exc))
        return {
            "title":     question[:80],
            "x_label":   columns[0] if columns else "",
            "y_label":   columns[1] if len(columns) > 1 else "",
            "rationale": f"{chart_type} selected by data-shape rules.",
        }


# ═════════════════════════════════════════════════════════════════════════════
# Step 4 — Figure Builder
# ═════════════════════════════════════════════════════════════════════════════

def _build_figure(
    chart_type: str,
    raw_data: list,
    columns: list,
    profile: dict[str, Any],
    layout_meta: dict[str, str],
) -> dict[str, Any]:
    rows          = profile["rows"][:50]
    numeric_cols  = profile["numeric_cols"]
    temporal_cols = profile["temporal_cols"]
    cat_cols      = profile["cat_cols"]

    title   = layout_meta.get("title", "")
    x_label = layout_meta.get("x_label", "")
    y_label = layout_meta.get("y_label", "")

    layout: dict[str, Any] = {
        "title": {"text": title},
        "xaxis": {"title": {"text": x_label}},
        "yaxis": {"title": {"text": y_label}},
    }

    # ── Indicator ─────────────────────────────────────────────────────────────
    if chart_type == "indicator":
        num_col = numeric_cols[0] if numeric_cols else (columns[0] if columns else "Value")
        value   = _coerce_float(rows[0].get(num_col)) if rows else 0
        return {
            "data": [{"type": "indicator", "mode": "number", "value": value or 0,
                      "title": {"text": title or num_col, "font": {"size": 20}},
                      "number": {"font": {"color": _FONT_COLOR, "size": 48}}}],
            "layout": {"title": {"text": ""}},
        }

    # ── Histogram ─────────────────────────────────────────────────────────────
    if chart_type == "histogram":
        num_col = numeric_cols[0]
        values  = [_coerce_float(r.get(num_col)) for r in rows]
        values  = [v for v in values if v is not None]
        return {
            "data": [{"type": "histogram", "x": values, "name": num_col, "nbinsx": 20}],
            "layout": {**layout, "bargap": 0.05},
        }

    # ── Line / Multi-Line / Scatter ───────────────────────────────────────────
    if chart_type in ("line", "multi_line", "scatter"):
        x_col  = temporal_cols[0] if temporal_cols else (cat_cols[0] if cat_cols else columns[0])
        # For multi-line, use all numeric columns. For scatter/line, use the primary one.
        target_y_cols = numeric_cols if chart_type == "multi_line" else ([numeric_cols[0]] if numeric_cols else [columns[-1]])
        
        traces = []
        for i, y_col in enumerate(target_y_cols):
            x_vals = [str(r.get(x_col, "")) for r in rows]
            y_vals = [_coerce_float(r.get(y_col)) for r in rows]
            
            mode = "lines+markers" if (temporal_cols or chart_type in ("line", "multi_line")) else "markers"
            trace = {
                "type": "scatter",
                "mode": mode,
                "x": x_vals, "y": y_vals, "name": y_col,
                "marker": {"size": 8} if mode == "markers" else {"size": 6}
            }
            
            # Dual-Axis logic
            if chart_type == "multi_line" and len(target_y_cols) == 2 and i == 1:
                v1_max = profile.get("numeric_range", {}).get(target_y_cols[0], {}).get("max", 1)
                v2_max = profile.get("numeric_range", {}).get(target_y_cols[1], {}).get("max", 1)
                if v1_max > 0 and v2_max > 0 and (v1_max / v2_max > 10 or v2_max / v1_max > 10):
                    trace["yaxis"] = "y2"
                    layout["yaxis2"] = {
                        "title": {"text": y_col},
                        "overlaying": "y",
                        "side": "right",
                        "gridcolor": _TRANSPARENT,
                        "tickfont": {"color": _FONT_COLOR}
                    }
            
            traces.append(trace)

        return {
            "data": traces,
            "layout": layout,
        }

    # ── Vertical Bar ─────────────────────────────────────────────────────────
    if chart_type == "bar":
        x_col  = cat_cols[0]     if cat_cols     else columns[0]
        y_col  = numeric_cols[0] if numeric_cols else columns[-1]
        x_vals = [str(r.get(x_col, "")) for r in rows]
        y_vals = [_coerce_float(r.get(y_col)) or 0 for r in rows]
        pairs  = sorted(zip(x_vals, y_vals), key=lambda p: p[1], reverse=True)
        x_vals, y_vals = zip(*pairs) if pairs else ([], [])
        return {
            "data": [{"type": "bar", "x": list(x_vals), "y": list(y_vals),
                      "name": y_col, "orientation": "v"}],
            "layout": layout,
        }

    # ── [FIX-3] Horizontal Bar ────────────────────────────────────────────────
    if chart_type == "h_bar":
        x_col  = cat_cols[0]     if cat_cols     else columns[0]
        y_col  = numeric_cols[0] if numeric_cols else columns[-1]
        labels = [str(r.get(x_col, "")) for r in rows]
        values = [_coerce_float(r.get(y_col)) or 0 for r in rows]
        # Sort ascending لأن h_bar بيعرض من أسفل لفوق
        pairs  = sorted(zip(labels, values), key=lambda p: p[1])
        labels, values = zip(*pairs) if pairs else ([], [])
        h_layout = {
            **layout,
            "xaxis": {"title": {"text": y_label}},  # flip labels for horizontal
            "yaxis": {"title": {"text": x_label}, "automargin": True},
            "margin": {"l": 160, "r": 30, "t": 60, "b": 60},  # wider left margin for labels
        }
        return {
            "data": [{"type": "bar", "x": list(values), "y": list(labels),
                      "name": y_col, "orientation": "h"}],
            "layout": h_layout,
        }

    # ── [FIX-4] Dot Plot (narrow range) ──────────────────────────────────────
    if chart_type == "dot_plot":
        x_col  = cat_cols[0]     if cat_cols     else columns[0]
        y_col  = numeric_cols[0] if numeric_cols else columns[-1]
        labels = [str(r.get(x_col, "")) for r in rows]
        values = [_coerce_float(r.get(y_col)) or 0 for r in rows]
        # Sort descending
        pairs  = sorted(zip(labels, values), key=lambda p: p[1], reverse=True)
        labels, values = zip(*pairs) if pairs else ([], [])

        rng    = profile.get("numeric_range", {}).get(y_col, {})
        mn, mx = rng.get("min", min(values)), rng.get("max", max(values))
        padding = (mx - mn) * 0.15 or 1  # add 15% padding so dots don't hug edges

        dot_layout = {
            **layout,
            # [FIX-4] Set axis range to honest zoom — show actual spread, not from 0
            "xaxis": {
                "title": {"text": y_label},
                "range": [mn - padding, mx + padding],
                "automargin": True,
            },
            "yaxis": {
                "title": {"text": x_label},
                "automargin": True,
            },
            "margin": {"l": 160, "r": 30, "t": 60, "b": 60},
        }
        return {
            "data": [{
                "type":   "scatter",
                "mode":   "markers",
                "x":      list(values),
                "y":      list(labels),
                "marker": {
                    "size":  14,
                    "color": _COLORWAY[0],
                    "line":  {"color": "rgba(255,255,255,0.4)", "width": 1.5},
                },
                "name": y_col,
                "text": [f"{v:.2f}" for v in values],
                "hovertemplate": "<b>%{y}</b><br>%{x:.2f}<extra></extra>",
            }],
            "layout": dot_layout,
        }

    # ── Pie / Donut ───────────────────────────────────────────────────────────
    if chart_type == "pie":
        label_col = cat_cols[0]     if cat_cols     else columns[0]
        value_col = numeric_cols[0] if numeric_cols else columns[-1]
        labels    = [str(r.get(label_col, "")) for r in rows]
        values    = [_coerce_float(r.get(value_col)) or 0 for r in rows]
        return {
            "data": [{"type": "pie", "labels": labels, "values": values,
                      "hole": 0.45, "name": value_col}],
            "layout": {"title": {"text": title}},
        }

    # ── Treemap ───────────────────────────────────────────────────────────────
    if chart_type == "treemap":
        label_col = cat_cols[0]     if cat_cols     else columns[0]
        value_col = numeric_cols[0] if numeric_cols else columns[-1]
        labels    = [str(r.get(label_col, "")) for r in rows]
        values    = [_coerce_float(r.get(value_col)) or 0 for r in rows]
        parents   = [""] * len(labels)
        return {
            "data": [{"type": "treemap", "labels": labels,
                      "parents": parents, "values": values}],
            "layout": {"title": {"text": title}},
        }

    # ── Table (fallback) ──────────────────────────────────────────────────────
    return _build_fallback_table({"columns": columns, "data": raw_data})


# ═════════════════════════════════════════════════════════════════════════════
# Step 5 — Validation
# ═════════════════════════════════════════════════════════════════════════════

def _validate_figure(figure: dict[str, Any]) -> str | None:
    if not isinstance(figure, dict):
        return "figure is not a dict"

    traces = figure.get("data")
    if not traces or not isinstance(traces, list):
        return "figure.data is missing or empty"

    for i, trace in enumerate(traces):
        if not isinstance(trace, dict):
            return f"trace[{i}] is not a dict"

        trace_type = trace.get("type")
        if not trace_type:
            return f"trace[{i}] missing 'type'"

        if trace_type in ("bar", "scatter"):
            x = trace.get("x") or []
            y = trace.get("y") or []
            if not x or not y:
                return f"trace[{i}] ({trace_type}) has empty x or y arrays"
            if len(x) != len(y):
                return f"trace[{i}] ({trace_type}) x/y length mismatch: {len(x)} vs {len(y)}"

        elif trace_type == "pie":
            if not (trace.get("labels") and trace.get("values")):
                return f"trace[{i}] (pie) missing labels or values"
            if len(trace["labels"]) != len(trace["values"]):
                return f"trace[{i}] (pie) labels/values length mismatch"

        elif trace_type == "indicator":
            if trace.get("value") is None:
                return f"trace[{i}] (indicator) missing value"

        elif trace_type == "histogram":
            if not trace.get("x"):
                return f"trace[{i}] (histogram) empty x array"

    return None


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _no_chart(reason: str | None) -> dict[str, Any]:
    return {"chart_json": None, "chart_engine": "plotly",
            "viz_rationale": reason, "error": reason}


def _sanitize_question(q: str) -> str:
    try:
        parsed = json.loads(q)
        if isinstance(parsed, dict) and "text" in parsed:
            return parsed["text"]
    except (json.JSONDecodeError, TypeError):
        pass
    return q


def _build_fallback_table(analysis: dict[str, Any]) -> dict[str, Any]:
    columns = analysis.get("columns", [])
    rows    = analysis.get("data", [])[:50]
    norm    = _normalise_rows(rows, columns)

    cell_values = [[r.get(c, "") for r in norm] for c in columns]

    return {
        "data": [{
            "type": "table",
            "header": {
                "values":  columns,
                "fill":    {"color": "rgba(99,102,241,0.25)"},
                "font":    {"color": _FONT_COLOR, "size": 12},
                "align":   "left",
                "line":    {"color": "rgba(255,255,255,0.08)"},
            },
            "cells": {
                "values":  cell_values,
                "fill":    {"color": ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.01)"]},
                "font":    {"color": _FONT_COLOR, "size": 12},
                "align":   "left",
                "line":    {"color": "rgba(255,255,255,0.05)"},
            },
        }],
        "layout": {"title": {"text": "Query Results"}},
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _parse_json(content: Any) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        return {}

    content   = content.strip()
    start_idx = content.find("{")
    end_idx   = content.rfind("}")

    if start_idx == -1 or end_idx == -1:
        return {}

    json_str = content[start_idx: end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    try:
        cleaned = re.sub(r",\s*([\]}])", r"\1", json_str)
        cleaned = re.sub(r"[\x00-\x1F\x7F]", "", cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    return {}