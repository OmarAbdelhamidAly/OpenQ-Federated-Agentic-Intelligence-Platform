import json
import uuid
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState
from app.modules.json.tools.superset_client import (
    get_superset_client,
    get_or_create_database,
    create_virtual_dataset,
    create_chart,
    create_dashboard
)
from app.modules.json.tools.load_data_source import get_connection_string

SUPERSET_VIZ_PROMPT = """You are a Principal Data Scientist and Lead Visualization Architect.
Your core directive is to automatically configure premium, highly-insightful Apache Superset dashboards for JSON data.

### CHART INTELLIGENCE & SELECTION HEURISTICS
Choose from:
- echarts_timeseries_bar, echarts_timeseries_line, echarts_area, pie, table, big_number_total, treemap_v2, sunburst_v2, radar, bubble.

### EXECUTION DIRECTIVES
- Return ONLY a valid JSON object with "viz_type" and "params".
- No markdown formatting.
"""

async def visualization_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate a Superset Chart and Dashboard dynamically for JSON data."""
    analysis = state.get("analysis_results") or {}
    if not analysis or not analysis.get("data"):
        return {"chart_json": None}

    llm = get_llm(temperature=0)
    data_sample = analysis["data"][:10]
    
    prompt = SUPERSET_VIZ_PROMPT + f"\n\nIntent: {state.get('intent')}\nQuestion: {state.get('question')}\nColumns: {json.dumps(analysis.get('columns', []))}\nData: {json.dumps(data_sample, indent=2, default=str)}"

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        chart_config = json.loads(content)

        if not chart_config or "viz_type" not in chart_config or "params" not in chart_config:
            chart_config = {"viz_type": "table", "params": {"all_columns": analysis.get("columns", [])}}
        
        chart_config["params"]["color_scheme"] = "supersetColors"
            
        client = await get_superset_client()
        try:
            conn_string = get_connection_string(state)
            if not conn_string:
                from app.infrastructure.config import settings
                conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

            db_id = await get_or_create_database(client, f"Analytic DB {state.get('source_id')}", conn_string)
            
            table_name = state.get("table_name")
            if not table_name:
                table_name = f"json_{str(state.get('source_id', 'default')).replace('-', '_')}"
            
            # The worker-json analysis_agent returns transformed data (forecast, aggregate, etc.) in `analysis["data"]`.
            # To chart this transformed data in Superset, we must ingest it back into Postgres as a new table.
            import pandas as pd
            from sqlalchemy import create_engine
            
            res_table_name = f"res_{str(uuid.uuid4())[:8]}"
            df = pd.DataFrame(analysis["data"])
            
            # Convert any complex types to string before saving
            for c in df.columns:
                if df[c].dtype == 'object':
                    df[c] = df[c].astype(str)
                    
            engine = create_engine(conn_string)
            df.to_sql(res_table_name, engine, if_exists='replace', index=False)
            
            sql = f"SELECT * FROM {res_table_name}"
            v_table_name = f"v_ds_{str(uuid.uuid4())[:8]}"
            dataset_id = await create_virtual_dataset(client, db_id, sql=sql, table_name=v_table_name)
            
            dashboard_id, internal_uuid, embedded_uuid = await create_dashboard(client, state.get("question", "JSON Analysis Dashboard"))
            await create_chart(client, dataset_id, state.get("question", "Chart"), chart_config["viz_type"], chart_config["params"], dashboard_id=dashboard_id)

            return {
                "chart_json": {"embedded_id": embedded_uuid, "native_id": dashboard_id, "internal_uuid": internal_uuid}, 
                "chart_engine": "superset"
            }
        finally:
            await client.aclose()

    except Exception as e:
        logger.error("json_superset_failed", error=str(e))
        return {"chart_json": None, "error": str(e)}
