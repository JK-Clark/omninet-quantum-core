# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/license_manager.py — License tier logic for OmniNet Quantum-Core

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas

# Hardcoded valid test keys  {key: (tier, device_limit)}
VALID_KEYS = {
    "TRIAL-OMNINET-2026": ("trial", 10),
    "COMMUNITY-GENIO-ELITE": ("community", None),
    "BANK-QUANTUM-SECURE": ("bank", None),
}

TIER_DURATIONS = {
    "trial": timedelta(days=7),
    "community": None,  # unlimited
    "bank": None,
}


def get_license_status(db: Session) -> schemas.LicenseStatus:
    """Return the active license or a default trial if none exists."""
    license_row = db.query(models.License).filter(models.License.is_active == True).first()

    if license_row is None:
        # Return default trial
        return schemas.LicenseStatus(
            tier="trial",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=7),
            device_limit=10,
        )

    return schemas.LicenseStatus(
        tier=license_row.tier,
        is_active=license_row.is_active,
        expires_at=license_row.expires_at,
        device_limit=license_row.device_limit,
    )


def activate_license(key: str, user_id: int, db: Session) -> schemas.LicenseStatus:
    """Validate and activate a license key."""
    if key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid license key",
        )

    tier, device_limit = VALID_KEYS[key]

    # Deactivate any existing active license
    db.query(models.License).filter(models.License.is_active == True).update({"is_active": False})

    duration = TIER_DURATIONS.get(tier)
    expires_at = datetime.utcnow() + duration if duration else None

    # Upsert the license record
    existing = db.query(models.License).filter(models.License.key == key).first()
    if existing:
        existing.is_active = True
        existing.expires_at = expires_at
        existing.activated_by = user_id
        existing.activated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
    else:
        new_license = models.License(
            key=key,
            tier=tier,
            is_active=True,
            expires_at=expires_at,
            device_limit=device_limit,
            activated_by=user_id,
            activated_at=datetime.utcnow(),
        )
        db.add(new_license)
        db.commit()
        db.refresh(new_license)

    return get_license_status(db)


def ensure_default_license(db: Session) -> None:
    """Insert a trial license if no license exists in the database."""
    if db.query(models.License).count() == 0:
        trial = models.License(
            key="TRIAL-OMNINET-2026",
            tier="trial",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=7),
            device_limit=10,
        )
        db.add(trial)
        db.commit()
