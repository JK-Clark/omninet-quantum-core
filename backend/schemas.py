# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/schemas.py — Pydantic v2 schemas for OmniNet Quantum-Core

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


# ── License ───────────────────────────────────────────────────────────────────

class LicenseStatus(BaseModel):
    tier: str
    is_active: bool
    expires_at: Optional[datetime]
    device_limit: Optional[int]

    model_config = {"from_attributes": True}


class LicenseActivate(BaseModel):
    key: str


# ── Device ────────────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    hostname: str
    ip_address: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    status: str = "up"
    topology_x: float = 0.0
    topology_y: float = 0.0


class DeviceResponse(BaseModel):
    id: int
    hostname: str
    ip_address: str
    device_type: Optional[str]
    vendor: Optional[str]
    model: Optional[str]
    status: str
    last_seen: Optional[datetime]
    topology_x: float
    topology_y: float

    model_config = {"from_attributes": True}


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: int
    device_id: int
    severity: str
    message: str
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Topology ──────────────────────────────────────────────────────────────────

class TopologyNode(BaseModel):
    id: str
    data: Dict[str, Any]
    position: Dict[str, float]
    type: str = "default"


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None


class TopologyResponse(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]


# ── AI Predictions ────────────────────────────────────────────────────────────

class AIpredictionResponse(BaseModel):
    id: int
    device_id: int
    health_score: float
    predicted_failure_at: Optional[datetime]
    confidence: Optional[float]
    recommendation: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthTimelinePoint(BaseModel):
    timestamp: datetime
    health_score: float


class HealthTimeline(BaseModel):
    device_id: int
    timeline: List[HealthTimelinePoint]


# ── Discover ──────────────────────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    cidr: str
    username: str
    password: str
    device_type: str = "cisco_ios"


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
