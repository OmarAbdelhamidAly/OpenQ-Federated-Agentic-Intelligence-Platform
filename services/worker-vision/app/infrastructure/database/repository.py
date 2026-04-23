"""Repository for Vision database operations."""
from __future__ import annotations
import uuid
from typing import List, Dict, Any
from sqlalchemy import select
from app.infrastructure.database import async_session_factory
from app.models.vision import VisionCamera, VisionFaceEmbedding, VisionLog

class VisionRepository:
    async def get_all_cameras(self) -> List[VisionCamera]:
        async with async_session_factory() as db:
            res = await db.execute(select(VisionCamera).where(VisionCamera.status == "active"))
            return res.scalars().all()

    async def get_all_embeddings(self) -> List[Dict[str, Any]]:
        async with async_session_factory() as db:
            res = await db.execute(select(VisionFaceEmbedding))
            embeddings = res.scalars().all()
            return [{"user_id": e.user_id, "embedding": e.embedding} for e in embeddings]

    async def save_logs(self, tenant_id: uuid.UUID, camera_id: uuid.UUID, logs: List[Dict[str, Any]]):
        async with async_session_factory() as db:
            for log_data in logs:
                if not log_data["user_id"]:
                    continue # Don't save logs for unidentified people for now
                    
                log = VisionLog(
                    tenant_id=tenant_id,
                    user_id=log_data["user_id"],
                    camera_id=camera_id,
                    activity=log_data["activity"],
                    engagement_score=log_data["engagement_score"]
                )
                db.add(log)
            await db.commit()
