import json
import uuid
import structlog
from typing import Any, Dict

logger = structlog.get_logger(__name__)

from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState
from app.modules.csv.tools.superset_client import (
    get_superset_client,
    get_or_create_database,
    create_virtual_dataset,
    create_chart,
    create_dashboard
)
from app.modules.csv.tools.load_data_source import get_connection_string

SUPERSET_VIZ_PROMPT = """You are a Principal Data Scientist and Lead Visualization Architect.
Your core directive is to automatically configure premium, highly-insightful Apache Superset dashboards for CSV data.

### CHART INTELLIGENCE & SELECTION HEURISTICS
Apply the same heuristics as for SQL data. Choose from:
- echarts_timeseries_bar, echarts_timeseries_line, echarts_area, pie, table, big_number_total, treemap_v2, sunburst_v2, radar, bubble.

### EXECUTION DIRECTIVES
- Return ONLY a valid JSON object with "viz_type" and "params".
- No markdown formatting.
"""

async def visualization_agent(state: AnalysisState) -> Dict[str, Any]:
    """Generate a Superset Chart and Dashboard dynamically for CSV data."""
    analysis = state.get("analysis_results") or {}
    if not analysis or not analysis.get("data"):
        return {"chart_json": None}

    llm = get_llm(temperature=0)
    data_sample = analysis["data"][:10]
    
    prompt = SUPERSET_VIZ_PROMPT + f"\n\nIntent: {state.get('intent')}\nQuestion: {state.get('question')}\nColumns: {json.dumps(analysis.get('columns', []))}\nData: {json.dumps(data_sample, indent=2, default=str)}"

    try:
        response = await llm.ainvoke(prompt)
        chart_config = _parse_json(response.content)

        if not chart_config or "viz_type" not in chart_config or "params" not in chart_config:
            chart_config = {"viz_type": "table", "params": {"all_columns": analysis.get("columns", [])}}
        
        # Add color scheme
        chart_config["params"]["color_scheme"] = "supersetColors"
            
        client = await get_superset_client()
        try:
            # The worker-csv analysis_agent returns transformed data (forecast, etc.) in `analysis["data"]`.
            # To chart this transformed data in Superset, we must ingest it back into Postgres as a new table.
            conn_string = get_connection_string(state)
            db_id = await get_or_create_database(client, f"Analytic DB {state.get('source_id')}", conn_string)
            
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
            dataset_id = await create_virtual_dataset(client, db_id, sql=sql, table_name=f"ds_{str(uuid.uuid4())[:8]}")
            
            dashboard_id, internal_uuid, embedded_uuid = await create_dashboard(client, state.get("question", "CSV Analysis Dashboard"))
            await create_chart(client, dataset_id, state.get("question", "Chart"), chart_config["viz_type"], chart_config["params"], dashboard_id=dashboard_id)

            return {
                "chart_json": {"embedded_id": embedded_uuid, "native_id": dashboard_id, "internal_uuid": internal_uuid}, 
                "chart_engine": "superset"
            }
        finally:
            await client.aclose()

    except Exception as e:
        logger.error("csv_superset_failed", error=str(e))
        return {"chart_json": None, "error": str(e)}

def _parse_json(content: str) -> Dict[str, Any]:
    # Reuse parsing logic...
    try:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            return json.loads(content[start:end+1])
    except:
        pass
    return {}
