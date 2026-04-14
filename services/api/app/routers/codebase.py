import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.database.postgres import get_db
from app.infrastructure.api_dependencies import get_current_user, verify_permission
from app.models.user import User
from app.models.data_source import DataSource
from app.schemas.codebase import CodeGraphResponse
from app.infrastructure.adapters.neo4j import Neo4jAdapter

router = APIRouter(prefix="/api/v1/codebase", tags=["codebase"])

@router.get("/{source_id}/graph", response_model=CodeGraphResponse)
async def get_codebase_graph(
    source_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CodeGraphResponse:
    """Fetch the structural graph for a specific codebase source (Nodes & Edges)."""
    
    # 1. Verify existence in Postgres and tenant ownership
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.tenant_id == current_user.tenant_id
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
        
    if source.type != "codebase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not a codebase",
        )

    # 2. Verify IAM permissions
    await verify_permission("query", str(source_id), current_user, db)

    # 3. Fetch from Neo4j
    adapter = Neo4jAdapter()
    try:
        data = adapter.get_graph_data(str(source_id))
        return CodeGraphResponse(**data)
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("neo4j_graph_fetch_failed", error=str(e), source_id=str(source_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph data: {str(e)}"
        )
