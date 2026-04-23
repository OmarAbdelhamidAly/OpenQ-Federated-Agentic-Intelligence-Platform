"""Domain entities for Vision service."""
from __future__ import annotations
from typing import Dict, List, Optional, Any, TypedDict
import uuid
from datetime import datetime

class VisionState(TypedDict, total=False):
    """State of a single vision processing cycle."""
    camera_id: uuid.UUID
    tenant_id: uuid.UUID
    frame: Any  # numpy.ndarray
    timestamp: datetime
    
    # Analysis results
    detections: List[Dict[str, Any]]
    known_faces: List[Dict[str, Any]]
    
    # Final Output
    logs_to_save: List[Dict[str, Any]]
    error: Optional[str]

class DetectionEntity(TypedDict):
    """Represents a single detection in a frame."""
    user_id: Optional[uuid.UUID]
    activity: str
    focus_score: float
    bbox: List[int]
    confidence: float
