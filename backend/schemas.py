import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    license_tier: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ─── Device ──────────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    hostname: str
    ip_address: str
    device_type: str = "unknown"
    vendor: str = "unknown"
    os_version: Optional[str] = None


class DeviceOut(BaseModel):
    id: int
    hostname: str
    ip_address: str
    device_type: str
    vendor: str
    os_version: Optional[str]
    status: str
    last_seen: Optional[datetime.datetime]
    neighbors: Optional[Any]

    model_config = {"from_attributes": True}


# ─── License ─────────────────────────────────────────────────────────────────

class LicenseActivateRequest(BaseModel):
    key: str


class LicenseOut(BaseModel):
    id: int
    key: str
    tier: str
    activated_at: Optional[datetime.datetime]
    expires_at: Optional[datetime.datetime]
    max_devices: Optional[int]
    is_active: bool

    model_config = {"from_attributes": True}


class LicenseStatusResponse(BaseModel):
    tier: str
    is_active: bool
    expires_at: Optional[datetime.datetime]
    max_devices: Optional[int]
    days_remaining: Optional[int]


# ─── Alert ───────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    device_id: int
    severity: str
    message: str
    predicted_at: datetime.datetime
    resolved_at: Optional[datetime.datetime]
    is_resolved: bool

    model_config = {"from_attributes": True}


# ─── Topology ────────────────────────────────────────────────────────────────

class TopologyLinkOut(BaseModel):
    id: int
    source_device_id: int
    target_device_id: int
    link_type: str
    bandwidth: Optional[float]
    latency: Optional[float]

    model_config = {"from_attributes": True}


class TopologyMapResponse(BaseModel):
    nodes: List[DeviceOut]
    links: List[TopologyLinkOut]


class DiscoverRequest(BaseModel):
    seed_ip: str
    username: str
    password: str
    device_type: str = "cisco_ios"
    secret: str = ""


# ─── AI ──────────────────────────────────────────────────────────────────────

class PredictionResponse(BaseModel):
    device_id: int
    failure_probability: float
    time_to_failure_hours: Optional[float]
    alert_created: bool
    message: str


class MetricsPayload(BaseModel):
    cpu_percent: float
    ram_percent: float
    error_rate: float
    latency_ms: float


# ─── API Envelope ────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    status: str = "ok"
    data: Any = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class APIError(BaseModel):
    status: str = "error"
    error_code: str
    message: str
