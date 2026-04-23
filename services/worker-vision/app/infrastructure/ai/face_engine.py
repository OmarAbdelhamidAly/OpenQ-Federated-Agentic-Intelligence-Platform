"""Face Recognition infrastructure using DeepFace/FaceNet."""
from __future__ import annotations
import numpy as np
from deepface import DeepFace
from typing import List, Dict, Any, Optional
import uuid
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)

class FaceEngine:
    def __init__(self):
        self.detector_backend = 'opencv'
        self.recognition_model = 'Facenet'

    def get_embedding(self, img: np.ndarray) -> Optional[List[float]]:
        """Extract embedding from an image."""
        try:
            objs = DeepFace.represent(
                img_path=img,
                model_name=self.recognition_model,
                enforce_detection=False,
                detector_backend=self.detector_backend
            )
            if objs:
                return objs[0]["embedding"]
        except Exception as e:
            logger.error("face_embedding_failed", error=str(e))
        return None

    def find_match(self, current_emb: List[float], known_faces: List[Dict[str, Any]]) -> tuple[Optional[uuid.UUID], float]:
        """Find best match among known faces."""
        best_match_id = None
        highest_similarity = 0.0
        
        current_np = np.array(current_emb)
        
        for face in known_faces:
            known_np = np.array(face["embedding"])
            similarity = np.dot(current_np, known_np) / (np.linalg.norm(current_np) * np.linalg.norm(known_np))
            
            if similarity > settings.FACE_SIMILARITY_THRESHOLD and similarity > highest_similarity:
                highest_similarity = similarity
                best_match_id = face["user_id"]
                
        return best_match_id, float(highest_similarity)
