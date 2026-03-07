import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
import enum

from database import Base


class LicenseTierEnum(str, enum.Enum):
    TRIAL = "TRIAL"
    COMMUNITY = "COMMUNITY"
    BANK = "BANK"


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String(64), unique=True, index=True, nullable=False)
    email: str = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password: str = Column(String(255), nullable=False)
    license_tier: str = Column(
        Enum(LicenseTierEnum), default=LicenseTierEnum.TRIAL, nullable=False
    )
    created_at: datetime.datetime = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    is_active: bool = Column(Boolean, default=True, nullable=False)


class Device(Base):
    __tablename__ = "devices"

    id: int = Column(Integer, primary_key=True, index=True)
    hostname: str = Column(String(255), index=True, nullable=False)
    ip_address: str = Column(String(45), unique=True, index=True, nullable=False)
    device_type: str = Column(String(64), nullable=False, default="unknown")
    vendor: str = Column(String(64), nullable=False, default="unknown")
    os_version: str = Column(String(128), nullable=True)
    status: str = Column(String(32), default="unknown", nullable=False)
    last_seen: Optional[datetime.datetime] = Column(DateTime, nullable=True)
    neighbors: Optional[Dict[str, Any]] = Column(JSON, nullable=True, default=list)

    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    source_links = relationship(
        "TopologyLink",
        foreign_keys="TopologyLink.source_device_id",
        back_populates="source_device",
        cascade="all, delete-orphan",
    )
    target_links = relationship(
        "TopologyLink",
        foreign_keys="TopologyLink.target_device_id",
        back_populates="target_device",
        cascade="all, delete-orphan",
    )


class License(Base):
    __tablename__ = "licenses"

    id: int = Column(Integer, primary_key=True, index=True)
    # String(512) to accommodate the base64-payload + signature format used by
    # the hardware-locked Ed25519 licensing system.
    key: str = Column(String(512), unique=True, index=True, nullable=False)
    tier: str = Column(Enum(LicenseTierEnum), nullable=False)
    activated_at: Optional[datetime.datetime] = Column(DateTime, nullable=True)
    expires_at: Optional[datetime.datetime] = Column(DateTime, nullable=True)
    max_devices: Optional[int] = Column(Integer, nullable=True)
    # SHA-256 fingerprint (32 hex chars) of the server this license is bound to.
    hardware_id: Optional[str] = Column(String(64), nullable=True)
    # UTC timestamp of the most recent successful license tier evaluation.
    # Used for clock-rollback anti-fraud detection: if utcnow() is significantly
    # before this value the system clock has been wound back.
    last_checked_at: Optional[datetime.datetime] = Column(DateTime, nullable=True)
    is_active: bool = Column(Boolean, default=False, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: int = Column(Integer, primary_key=True, index=True)
    device_id: int = Column(Integer, ForeignKey("devices.id"), nullable=False)
    severity: str = Column(String(32), nullable=False, default="warning")
    message: str = Column(Text, nullable=False)
    predicted_at: datetime.datetime = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    resolved_at: Optional[datetime.datetime] = Column(DateTime, nullable=True)
    is_resolved: bool = Column(Boolean, default=False, nullable=False)

    device = relationship("Device", back_populates="alerts")


class TopologyLink(Base):
    __tablename__ = "topology_links"

    id: int = Column(Integer, primary_key=True, index=True)
    source_device_id: int = Column(Integer, ForeignKey("devices.id"), nullable=False)
    target_device_id: int = Column(Integer, ForeignKey("devices.id"), nullable=False)
    link_type: str = Column(String(64), nullable=False, default="ethernet")
    bandwidth: Optional[float] = Column(Float, nullable=True)
    latency: Optional[float] = Column(Float, nullable=True)

    source_device = relationship(
        "Device",
        foreign_keys=[source_device_id],
        back_populates="source_links",
    )
    target_device = relationship(
        "Device",
        foreign_keys=[target_device_id],
        back_populates="target_links",
    )

