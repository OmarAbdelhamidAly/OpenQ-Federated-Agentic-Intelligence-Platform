"""SQL Pipeline — Visualization Agent.

Generates Superset Datasets, Charts, and Dashboards dynamically.
"""

from __future__ import annotations

import json
import re
import uuid
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState
from app.modules.sql.tools.superset_client import (
    get_superset_client,
    get_or_create_database,
    create_virtual_dataset,
    create_chart,
    create_dashboard
)
from app.modules.sql.tools.load_data_source import get_connection_string

SUPERSET_VIZ_PROMPT = """You are a Principal Data Scientist and Lead Visualization Architect.
Your core directive is to automatically configure premium, highly-insightful Apache Superset dashboards.

### CHART INTELLIGENCE & SELECTION HEURISTICS
You have access to 10 distinguished Superset visualization archetypes. You MUST choose the single MOST statistically powerful chart to answer the user's question, applying these rules:
- **Time-Series / Trends**: Use Line or Area charts if the primary dimension is time/dates.
- **Categorical Comparisons**: Use Bar charts for 3-12 categories. Use Treemap for massive categorical segments.
- **Part-to-Whole / Hierarchies**: Use Pie (max 5 slices), or Sunburst if multiple hierarchical text columns exist.
- **Outliers & Correlations**: Use Bubble charts when comparing 3 continuous numeric metrics simultaneously.
- **Executive KPI**: Use Big Number when the answer is a single definitive total or an aggregate score.
- **Raw Data / Drill-Down**: Use Table ONLY if the user explicitly asks for a list, dump, or if no chart fits.

### THE 10 SUPERSET SCHEMAS
You MUST output a strict JSON object containing TWO keys: "viz_type" and "params".
The "viz_type" must be one of the identifiers below, and the "params" must match its exact schema.
Example: {{ "viz_type": "pie", "params": {{ "metric": "revenue", "groupby": ["region"] }} }}
Field definitions:
- "metrics" (list): Requires an array of numeric column names (e.g. ["revenue"]).
- "metric" (string): Requires a single numeric column name (e.g. "revenue").
- "groupby" (list): Requires an array of categorical/text column names.

47. "echarts_timeseries_bar" (Vertical Bar Chart)
   - params: {{ "metrics": ["<num>"], "groupby": ["<cat>"], "x_axis": "<cat>" }}
48. "echarts_timeseries_line" (Line Chart)
   - params: {{ "metrics": ["<num>"], "groupby": [], "x_axis": "<time_or_cat_col>" }}
49. "echarts_area" (Stacked Area Chart - great for cumulative trends)
   - params: {{ "metrics": ["<num>"], "groupby": ["<cat>"], "x_axis": "<time_or_cat_col>" }}
50. "pie" (Standard/Donut Pie Chart)
   - params: {{ "metric": "<num>", "groupby": ["<cat>"] }}
51. "table" (Data Table)
   - params: {{ "metrics": [], "groupby": [], "all_columns": ["<col1>", "<col2>", "<col3>"] }}
52. "big_number_total" (Executive KPI Indicator)
   - params: {{ "metric": "<num>" }}
53. "treemap_v2" (Nested Treemap - great for market share)
   - params: {{ "metrics": ["<num>"], "groupby": ["<cat1>", "<cat2>"] }}
54. "sunburst_v2" (Sunburst Hierarchy)
   - params: {{ "metric": "<num>", "groupby": ["<cat1>", "<cat2>"] }}
55. "radar" (Radar / Spider Chart - great for profiling entities)
   - params: {{ "metrics": ["<num1>", "<num2>"], "groupby": ["<cat_entity>"] }}
56. "bubble" (Bubble Scatter Plot)
   - params: {{ "entity": "<cat>", "x": "<num1>", "y": "<num2>", "size": "<num3>" }}

### EXECUTION DIRECTIVES
- NEVER fabricate column names. The `metrics` or `groupby` MUST correspond verbatim to the Schema/Columns provided below.
- Add `"color_scheme": "supersetColors"` inside `"params"` to ensure vibrant and professional chart colors.
- Return ONLY a valid JSON object.
- NO markdown formatting (no ```json). NO explanation. NO preamble.

**Query Result Summary**:
Intent: {intent}
User Question: {question}
SQL Query: {sql}
Schema/Columns: {columns}
Stochastic Data Sample: {data}
"""

async def visualization_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate a Superset Chart and Dashboard dynamically."""
    analysis = state.get("analysis_results") or {}
    if not analysis or not analysis.get("data"):
        return {"chart_json": None}

    llm = get_llm(temperature=0)
    data_sample = analysis["data"][:10]
    
    prompt = SUPERSET_VIZ_PROMPT.format(
        intent=state.get("intent", "comparison"),
        question=state.get("question", ""),
        sql=state.get("generated_sql", ""),
        columns=json.dumps(analysis.get("columns", [])),
        data=json.dumps(data_sample, indent=2, default=str),
    )

    content = None
    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        chart_config = _parse_json(content)

        if not chart_config or "viz_type" not in chart_config or "params" not in chart_config:
            logger.warning("invalid_superset_config", content=content)
            chart_config = {
                "viz_type": "table",
                "params": {"all_columns": analysis.get("columns", [])}
            }
        
        # Normalize metrics: Superset virtual datasets need full aggregation objects,
        # not plain column name strings.
        chart_config["params"] = _normalize_metrics(chart_config["params"])
        
        # Inject vibrant color scheme for premium aesthetics
        chart_config["params"]["color_scheme"] = "supersetColors"
            
        # Execute Superset Flow!
        conn_string = get_connection_string(state)
        if not conn_string:
            raise ValueError("No valid connection string found for Superset")
            
        chart_engine = "superset"
        
        # Connect to Superset API
        client = await get_superset_client()
        
        try:
            db_name = f"Analytic DB {state.get('source_id')}"
            db_id = await get_or_create_database(client, db_name, conn_string)
            
            # Short UUID for table name
            ds_id = str(uuid.uuid4())[:8]
            dataset_id = await create_virtual_dataset(
                client, 
                db_id, 
                sql=state.get("generated_sql"), 
                table_name=f"dataset_{ds_id}"
            )
            # Create Dashboard first (to get ID for linking)
            dashboard_id, internal_uuid, embedded_uuid = await create_dashboard(client, state.get("question", "Analysis Dashboard")[:250])

            # Create Chart slice (linking to dashboard)
            chart_id = await create_chart(
                client, 
                dataset_id, 
                slice_name=state.get("question", "Analysis Chart")[:250], 
                viz_type=chart_config["viz_type"], 
                params=chart_config["params"],
                dashboard_id=dashboard_id
            )
            
            return {
                "chart_json": {
                    "embedded_id": embedded_uuid, 
                    "native_id": dashboard_id,
                    "internal_uuid": internal_uuid
                }, 
                "chart_engine": "superset"
            }
            
        finally:
            await client.aclose()

    except Exception as e:
        logger.error("superset_generation_failed", error=str(e), content=content)
        return {"chart_json": None, "error": f"Superset rendering failed: {e}"}

def _make_metric(col_name: str) -> dict:
    """Wrap a column name as a Superset SIMPLE aggregation metric object."""
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": col_name},
        "aggregate": "SUM",
        "label": col_name,
        "hasCustomLabel": False,
        "optionName": f"metric_{col_name}"
    }

def _normalize_metrics(params: dict) -> dict:
    """
    Convert plain string metrics (e.g. "TrackCount") to Superset-compatible
    aggregation objects. Virtual datasets don't have pre-defined metrics, so
    they must be expressed as SIMPLE column aggregations.
    """
    if "metrics" in params:
        normalized = []
        for m in params["metrics"]:
            if isinstance(m, str):
                normalized.append(_make_metric(m))
            else:
                normalized.append(m)  # already an object
        params["metrics"] = normalized
    
    if "metric" in params and isinstance(params["metric"], str):
        params["metric"] = _make_metric(params["metric"])
    
    return params


def _parse_json(content: Any) -> Dict[str, Any]:
    """Ultra-resilient JSON parser for LLM responses."""
    if not isinstance(content, str) or not content.strip():
        return {}
    content = content.strip()
    start_idx = content.find('{')
    end_idx = content.rfind('}')
    
    if start_idx == -1 or end_idx == -1:
        return {}
        
    json_str = content[start_idx : end_idx + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
        
    try:
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass
    return {}
