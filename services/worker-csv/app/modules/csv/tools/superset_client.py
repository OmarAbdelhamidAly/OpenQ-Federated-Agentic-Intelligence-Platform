import os
import json
import httpx
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)

# Environment variables for Superset configuration
SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://superset:8088")
SUPERSET_ADMIN_USER = os.environ.get("SUPERSET_ADMIN_USER", "admin")
SUPERSET_ADMIN_PASS = os.environ.get("SUPERSET_ADMIN_PASS", "admin")

async def get_superset_client() -> httpx.AsyncClient:
    """Returns an authenticated httpx client with CSRF tokens for Superset."""
    client = httpx.AsyncClient(timeout=30.0)
    try:
        # 1. Login to get the access token
        resp_login = await client.post(
            f"{SUPERSET_URL}/api/v1/security/login",
            json={"username": SUPERSET_ADMIN_USER, "password": SUPERSET_ADMIN_PASS, "provider": "db"},
        )
        if resp_login.status_code != 200:
            logger.error("superset_login_failed", status=resp_login.status_code, body=resp_login.text)
            raise ValueError(f"Superset login failed: {resp_login.text}")
        
        access_token = resp_login.json()["access_token"]
        client.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Referer": SUPERSET_URL
        })
        return client
    except Exception as e:
        await client.aclose()
        raise e

async def get_or_create_database(client: httpx.AsyncClient, db_name: str, sqlalchemy_uri: str) -> int:
    """Finds or creates a database connection in Superset."""
    # Search for an existing database with the same name
    q = json.dumps({"filters": [{"col": "database_name", "opr": "eq", "value": db_name}]})
    resp = await client.get(f"{SUPERSET_URL}/api/v1/database/?q={q}")
    dbs = resp.json().get("result", [])
    if dbs:
        return dbs[0]["id"]
        
    # Create a new database connection if not found
    payload = {
        "database_name": db_name,
        "sqlalchemy_uri": sqlalchemy_uri,
        "extra": json.dumps({"allows_virtual_table_explore": True})
    }
    resp = await client.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if resp.status_code not in (200, 201):
        raise ValueError(f"Failed to create Superset DB: {resp.text}")
        
    return resp.json()["id"]

async def create_virtual_dataset(client: httpx.AsyncClient, db_id: int, sql: str, table_name: str) -> int:
    """Creates a virtual dataset (SQL query) in Superset."""
    payload = {
        "database": db_id,
        "table_name": table_name,
        "sql": sql,
        "owners": [1]  # Explicitly assign to admin
    }
    resp = await client.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if resp.status_code not in (200, 201):
        raise ValueError(f"Failed to create Superset Virtual Dataset: {resp.text}")
    return resp.json()["id"]

async def create_chart(client: httpx.AsyncClient, dataset_id: int, slice_name: str, viz_type: str, params: dict, dashboard_id: Optional[int] = None) -> int:
    """Creates a chart slice using the dataset and LLM params."""
    params["datasource"] = f"{dataset_id}__table"
    params["viz_type"] = viz_type
    
    payload = {
        "slice_name": slice_name,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": viz_type,
        "params": json.dumps(params),
        "owners": [1]
    }
    if dashboard_id:
        payload["dashboards"] = [dashboard_id]
        
    resp = await client.post(f"{SUPERSET_URL}/api/v1/chart/", json=payload)
    if resp.status_code not in (200, 201):
        raise ValueError(f"Failed to create Superset Chart: {resp.text}")
    return resp.json()["id"]

async def create_dashboard(client: httpx.AsyncClient, dashboard_title: str) -> tuple[int, str, str]:
    """Creates a dashboard, enables embedding, and returns IDs/UUIDs."""
    # 1. Create Dashboard
    payload = {
        "dashboard_title": dashboard_title,
        "published": True,
        "owners": [1]
    }
    resp = await client.post(f"{SUPERSET_URL}/api/v1/dashboard/", json=payload)
    if resp.status_code not in (200, 201):
        raise ValueError(f"Failed to create Dashboard: {resp.text}")
        
    dashboard_id = resp.json()["id"]
    
    # 2. Get Internal UUID
    resp_dash = await client.get(f"{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}")
    internal_uuid = resp_dash.json()["result"]["uuid"]
    
    # 3. Enable/Get Embedding
    embed_payload = {"allowed_domains": []}
    resp_embed = await client.post(f"{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}/embedded", json=embed_payload)
    
    embedded_uuid = None
    if resp_embed.status_code in (200, 201):
        data = resp_embed.json()
        embedded_uuid = data.get("result", {}).get("uuid") or data.get("uuid")
            
    if not embedded_uuid:
        embedded_uuid = internal_uuid # Fallback
        
    return dashboard_id, internal_uuid, embedded_uuid
