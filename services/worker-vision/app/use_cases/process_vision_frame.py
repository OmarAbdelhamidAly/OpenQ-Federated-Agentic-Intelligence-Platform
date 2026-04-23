"""Use case to process a vision frame and generate tracking logs."""
from __future__ import annotations
import numpy as np
import structlog
from typing import Dict, Any, List

from app.domain.vision.entities import VisionState
from app.infrastructure.ai.yolo_engine import YOLOEngine
from app.infrastructure.ai.face_engine import FaceEngine

logger = structlog.get_logger(__name__)

class ProcessVisionFrame:
    def __init__(self, yolo: YOLOEngine, face: FaceEngine):
        self.yolo = yolo
        self.face = face

    async def execute(self, state: VisionState) -> VisionState:
        """Execute the vision analysis pipeline."""
        frame = state["frame"]
        known_faces = state.get("known_faces", [])
        
        # 1. Detection
        yolo_results = self.yolo.detect_persons(frame)
        
        logs = []
        for box in yolo_results.boxes:
            label = yolo_results.names[int(box.cls[0])]
            
            if label == "person":
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                person_crop = frame[y1:y2, x1:x2]
                
                # 2. Identification
                embedding = self.face.get_embedding(person_crop)
                user_id = None
                if embedding:
                    user_id, _ = self.face.find_match(embedding, known_faces)
                
                # 3. Activity (Simple logic for now)
                activity = "focused_work"
                for b in yolo_results.boxes:
                    if yolo_results.names[int(b.cls[0])] == "cell phone":
                        activity = "on_phone"
                
                logs.append({
                    "user_id": user_id,
                    "activity": activity,
                    "engagement_score": 0.95 if user_id else 0.0
                })
        
        state["logs_to_save"] = logs
        return state
