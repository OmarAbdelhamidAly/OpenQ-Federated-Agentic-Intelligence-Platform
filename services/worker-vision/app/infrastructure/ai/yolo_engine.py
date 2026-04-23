"""YOLO-based object detection infrastructure."""
from __future__ import annotations
from ultralytics import YOLO
import numpy as np
from app.core.config import settings

class YOLOEngine:
    def __init__(self):
        self.model = YOLO(settings.VISION_MODEL_YOLO)

    def detect_persons(self, frame: np.ndarray) -> list:
        """Detect persons and objects in a frame."""
        results = self.model(frame, verbose=False)[0]
        return results
