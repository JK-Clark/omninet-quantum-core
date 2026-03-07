# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
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
    hardware_id: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class LicenseStatusResponse(BaseModel):
    tier: str
    is_active: bool
    expires_at: Optional[datetime.datetime]
    max_devices: Optional[int]
    days_remaining: Optional[int]
    message: Optional[str] = None


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


# ─── Reports ──────────────────────────────────────────────────────────────────

class ReportGenerateRequest(BaseModel):
    lang: str = Field(
        default="EN",
        description="Report language: EN, FR, HI, or KO.",
        pattern="^(EN|FR|HI|KO)$",
    )


class ReportStatusResponse(BaseModel):
    status: str
    message: str
    lang: str
    generated_at: datetime.datetime


# ─── API Envelope ────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    status: str = "ok"
    data: Any = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class APIError(BaseModel):
    status: str = "error"
    error_code: str
    message: str


# ─── Server Health (Redfish / SNMP) ──────────────────────────────────────────

class ServerHealthRequest(BaseModel):
    ip_address: str = Field(..., description="BMC / OOB management IP address.")
    bmc_type: str = Field(
        ...,
        description="BMC type: 'idrac' (Dell iDRAC), 'ilo' (HP iLO), or 'imm' (IBM/Lenovo — SNMP).",
        pattern="^(idrac|ilo|imm)$",
    )
    username: Optional[str] = Field(
        default=None,
        description="BMC username (required for Redfish idrac/ilo).",
    )
    password: Optional[str] = Field(
        default=None,
        description="BMC password (required for Redfish idrac/ilo).",
    )
    snmp_community: Optional[str] = Field(
        default="public",
        description="SNMP community string (used only for bmc_type='imm').",
    )


class ServerHealthResponse(BaseModel):
    ip_address: str
    bmc_type: str
    overall_health: str
    system_model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    power_supplies: List[Dict[str, Any]] = Field(default_factory=list)
    fans: List[Dict[str, Any]] = Field(default_factory=list)
    temperatures: List[Dict[str, Any]] = Field(default_factory=list)
    drives: List[Dict[str, Any]] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)
