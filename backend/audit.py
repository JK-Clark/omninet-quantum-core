# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/audit.py — Structured audit trail module for OmniNet Quantum-Core

"""
Audit Trail Module
==================
Provides a persistent, structured audit log stored in the PostgreSQL
``audit_logs`` table.  All writes go through :func:`log_action`; the model
is registered with the shared ``Base`` so that :func:`database.create_tables`
creates the table automatically on startup.
"""

import json
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session

from database import Base


class AuditLog(Base):
    """SQLAlchemy model representing a single audit event."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def log_action(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[Any] = None,
) -> AuditLog:
    """Write a structured audit event to the ``audit_logs`` table.

    Args:
        db: SQLAlchemy session.
        action: Short action identifier, e.g. ``"user.login"`` or ``"device.created"``.
        user_id: ID of the user who triggered the event (nullable).
        resource_type: Type of the affected resource, e.g. ``"device"`` (nullable).
        resource_id: Primary-key of the affected resource (nullable).
        ip_address: Originating IP address of the request (nullable).
        details: Arbitrary extra data; dicts/lists are JSON-serialised automatically.

    Returns:
        The persisted :class:`AuditLog` instance.
    """
    details_str: Optional[str]
    if details is None:
        details_str = None
    elif isinstance(details, str):
        details_str = details
    else:
        details_str = json.dumps(details)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details_str,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_recent_logs(db: Session, limit: int = 100) -> List[AuditLog]:
    """Return the most recent audit log entries ordered by ``created_at`` DESC.

    Args:
        db: SQLAlchemy session.
        limit: Maximum number of entries to return (default: 100).

    Returns:
        List of :class:`AuditLog` instances, newest first.
    """
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
