"""Domain entities for Corporate service."""
from __future__ import annotations
from typing import Dict, List, Optional, Any, TypedDict
import uuid
from datetime import datetime

class StrategicState(TypedDict, total=False):
    """Overall state of strategic alignment."""
    tenant_id: uuid.UUID
    goals: List[Dict[str, Any]]
    policies: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    alignment_score: float
    analysis_report: str

class CorporateTaskEntity(TypedDict):
    """Represents a task in the organizational context."""
    id: uuid.UUID
    title: str
    status: str
    assignee_node_id: uuid.UUID
    creator_id: uuid.UUID
