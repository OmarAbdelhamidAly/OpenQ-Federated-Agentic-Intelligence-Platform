from __future__ import annotations
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class CodeNode(BaseModel):
    id: int
    type: str
    name: Optional[str] = None
    path: Optional[str] = None
    summary: Optional[str] = None

class CodeLink(BaseModel):
    source: int
    target: int
    type: str

class CodeGraphResponse(BaseModel):
    nodes: List[CodeNode]
    links: List[CodeLink]
