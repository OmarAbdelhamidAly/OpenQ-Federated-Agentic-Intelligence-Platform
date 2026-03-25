"""Superset integration router — provides guest tokens for embedded dashboards."""
from __future__ import annotations

import os
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from app.infrastructure.api_dependencies import get_current_user
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/superset", tags=["superset"])

SUPERSET_URL = os.getenv("SUPERSET_URL", "http://superset:8088")
SUPERSET_ADMIN_USER = os.getenv("SUPERSET_ADMIN_USER", "admin")
SUPERSET_ADMIN_PASS = os.getenv("SUPERSET_ADMIN_PASS", "admin")
SUPERSET_PUBLIC_URL = os.getenv("SUPERSET_PUBLIC_URL", "http://localhost:8088")


@router.get("/token")
async def get_superset_guest_token(
    dashboard_id: str = "analyst-main",
    current_user: User = Depends(get_current_user),
):
    """
    Returns a Superset guest token scoped to a specific dashboard.
    The frontend uses this token to embed the dashboard in an iframe.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Login to get Access Token
            resp_login = await client.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json={"username": SUPERSET_ADMIN_USER, "password": SUPERSET_ADMIN_PASS, "provider": "db"},
            )
            if resp_login.status_code != 200:
                logger.error("superset_login_failed", status=resp_login.status_code, body=resp_login.text[:200])
                raise HTTPException(status_code=502, detail="Could not authenticate with Superset")
            access_token = resp_login.json()["access_token"]

            # 2. Get CSRF Token
            resp_csrf = await client.get(
                f"{SUPERSET_URL}/api/v1/security/csrf_token/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp_csrf.status_code != 200:
                logger.error("superset_csrf_failed", status=resp_csrf.status_code, body=resp_csrf.text[:200])
                raise HTTPException(status_code=502, detail="Could not get CSRF token from Superset")
            csrf_token = resp_csrf.json()["result"]

            # 3. Create Guest Token
            # Superset expects the INTERNAL UUID (string) for resource matching in guest tokens
            # We ensure it is a string and potentially add the integer ID if we had it.
            # But since dashboard_id is already the internal_uuid (from frontend), we use it.
            
            resp_guest = await client.post(
                f"{SUPERSET_URL}/api/v1/security/guest_token/",
                json={
                    "user": {
                        "username": str(current_user.id),
                        "first_name": current_user.email.split("@")[0],
                        "last_name": "User",
                    },
                    "resources": [
                        {"type": "dashboard", "id": str(dashboard_id)}
                    ],
                    "roles": ["Gamma"],
                    "rls": [],
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-CSRFToken": csrf_token,
                    "Referer": SUPERSET_URL,
                },
            )
            if resp_guest.status_code != 200:
                logger.warning("superset_guest_token_failed", status=resp_guest.status_code, body=resp_guest.text[:200])
                raise HTTPException(status_code=502, detail="Could not create guest token")

            return {"guest_token": resp_guest.json()["token"], "superset_url": SUPERSET_PUBLIC_URL}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("superset_token_error", error=str(e))
        raise HTTPException(status_code=503, detail="Superset service unavailable")
