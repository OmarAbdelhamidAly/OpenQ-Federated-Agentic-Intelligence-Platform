"""Background worker for vision processing."""
from __future__ import annotations
import asyncio
import cv2
import structlog
from datetime import datetime, timezone

from app.core.config import settings
from app.infrastructure.database.repository import VisionRepository
from app.infrastructure.ai.yolo_engine import YOLOEngine
from app.infrastructure.ai.face_engine import FaceEngine
from app.use_cases.process_vision_frame import ProcessVisionFrame
from app.domain.vision.entities import VisionState

logger = structlog.get_logger(__name__)

class VisionWorker:
    def __init__(self):
        self.repo = VisionRepository()
        self.processor = ProcessVisionFrame(YOLOEngine(), FaceEngine())

    async def run_forever(self):
        """Main loop that samples cameras every X seconds."""
        logger.info("vision_worker_loop_started", interval=settings.SNAPSHOT_INTERVAL_SECONDS)
        
        while True:
            try:
                # 1. Fetch Context
                cameras = await self.repo.get_all_cameras()
                known_faces = await self.repo.get_all_embeddings()
                
                if not cameras:
                    logger.debug("no_active_cameras_found")
                else:
                    # 2. Process each camera
                    for camera in cameras:
                        await self._process_camera(camera, known_faces)
                
            except Exception as e:
                logger.error("worker_loop_error", error=str(e))
            
            await asyncio.sleep(settings.SNAPSHOT_INTERVAL_SECONDS)

    async def _process_camera(self, camera, known_faces):
        """Capture and process a single frame from a camera."""
        try:
            # Note: In production, we'd use a pool of RTSP clients
            # For this MVP, we open/capture/close
            cap = cv2.VideoCapture(camera.rtsp_url)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.warning("camera_capture_failed", camera_id=str(camera.id))
                return

            # 3. Use Case: Process Frame
            state: VisionState = {
                "camera_id": camera.id,
                "tenant_id": camera.tenant_id,
                "frame": frame,
                "timestamp": datetime.now(timezone.utc),
                "known_faces": known_faces
            }
            
            result_state = await self.processor.execute(state)
            
            # 4. Save Results
            if result_state.get("logs_to_save"):
                await self.repo.save_logs(
                    tenant_id=camera.tenant_id,
                    camera_id=camera.id,
                    logs=result_state["logs_to_save"]
                )
                logger.info("vision_logs_saved", camera_id=str(camera.id), count=len(result_state["logs_to_save"]))

        except Exception as e:
            logger.error("camera_processing_error", camera_id=str(camera.id), error=str(e))

vision_worker = VisionWorker()
