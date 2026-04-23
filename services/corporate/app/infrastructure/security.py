"""Security dependencies for role-based access control (RBAC)."""
from __future__ import annotations
from fastapi import Header, HTTPException, status
import structlog

logger = structlog.get_logger(__name__)

async def require_admin(x_user_role: str = Header(None)):
    """
    Dependency to ensure the user has 'admin' role.
    The api-gateway (api service) is expected to pass the X-User-Role header 
    after verifying the JWT.
    """
    if not x_user_role:
        logger.warning("missing_role_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user role information"
        )
        
    if x_user_role.lower() != "admin":
        logger.warning("unauthorized_access_attempt", role=x_user_role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    
    return x_user_role

async def require_user(x_user_role: str = Header(None)):
    """Ensures at least a valid user role is present."""
    if not x_user_role:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_user_role
