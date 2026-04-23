"""FastAPI entry point for Worker Vision Service."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio
import structlog
from fastapi import FastAPI, Depends, HTTPException

from app.infrastructure.database import engine, Base
from app.infrastructure.security import require_admin
from app.infrastructure.database.repository import VisionRepository
from app.models.vision import VisionCamera, VisionLog, VisionFaceEmbedding

logger = structlog.get_logger(__name__)
repo = VisionRepository()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Sync database tables and start background tasks."""
    logger.info("vision_service_starting")
    
    try:
        async with engine.begin() as conn:
            # Sync tables in the shared database
            await conn.run_sync(Base.metadata.create_all)
        logger.info("vision_db_tables_synced")
    except Exception as e:
        logger.error("vision_db_sync_failed", error=str(e))

    # Start Background Snapshot Engine
    from app.worker import vision_worker
    asyncio.create_task(vision_worker.run_forever())
    logger.info("background_vision_worker_task_created")
    
    yield
    logger.info("vision_service_shutting_down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenQ Vision Worker",
        description="Employee tracking and engagement analysis via computer vision.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "worker-vision"}

    @app.post("/cameras", dependencies=[Depends(require_admin)])
    async def add_camera(camera_data: dict):
        # Implementation for adding camera to DB
        return {"status": "camera_added"}

    @app.get("/logs/{user_id}", dependencies=[Depends(require_admin)])
    async def get_user_timeline(user_id: str, date: str):
        """Admin selects a person and a day to see their timeline."""
        # Implementation for querying logs
        return {"user_id": user_id, "date": date, "timeline": []}

    return app

app = create_app()
