# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/models.py — SQLAlchemy ORM models for OmniNet Quantum-Core

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    licenses = relationship("License", back_populates="activated_by_user", foreign_keys="License.activated_by")


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    tier = Column(String(50), nullable=False, default="trial")  # trial | community | bank
    is_active = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    device_limit = Column(Integer, nullable=True)
    activated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    activated_at = Column(DateTime, nullable=True)
    integrity_hash = Column(String(64), nullable=True)  # SHA-256 anti-tamper

    activated_by_user = relationship("User", back_populates="licenses", foreign_keys=[activated_by])


class LicenseAuditLog(Base):
    __tablename__ = "license_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    event = Column(String(50), nullable=False)  # activated | deactivated | tamper_detected | expired | access_denied
    license_key_hash = Column(String(64), nullable=True)  # SHA-256 of key (never the raw key)
    tier = Column(String(50), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(50), nullable=False, unique=True)
    device_type = Column(String(100), nullable=True)
    vendor = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    status = Column(String(20), default="up")  # up | down | warning
    last_seen = Column(DateTime, default=datetime.utcnow)
    topology_x = Column(Float, default=0.0)
    topology_y = Column(Float, default=0.0)

    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    predictions = relationship("AIprediction", back_populates="device", cascade="all, delete-orphan")
    topology_sources = relationship(
        "Topology",
        back_populates="source_device",
        foreign_keys="Topology.source_device_id",
        cascade="all, delete-orphan",
    )
    topology_targets = relationship(
        "Topology",
        back_populates="target_device",
        foreign_keys="Topology.target_device_id",
        cascade="all, delete-orphan",
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    severity = Column(String(20), nullable=False)  # critical | warning | info
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="alerts")


class Topology(Base):
    __tablename__ = "topology"

    id = Column(Integer, primary_key=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    target_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    link_type = Column(String(50), default="ethernet")
    bandwidth = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source_device = relationship("Device", back_populates="topology_sources", foreign_keys=[source_device_id])
    target_device = relationship("Device", back_populates="topology_targets", foreign_keys=[target_device_id])


class AIprediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    health_score = Column(Float, nullable=False)  # 0–100
    predicted_failure_at = Column(DateTime, nullable=True)
    confidence = Column(Float, nullable=True)  # 0.0–1.0
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="predictions")

