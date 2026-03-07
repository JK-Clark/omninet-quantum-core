"""
License management: tier validation, feature enforcement, and expiry checking.
"""

import datetime
import enum
import logging
import uuid
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

# Device limits per tier (None = unlimited)
TIER_DEVICE_LIMITS = {
    "TRIAL": 10,
    "COMMUNITY": None,
    "BANK": None,
}

# Days until trial expires from activation
TRIAL_DURATION_DAYS = 7

# Features and which tiers can access them
_FEATURE_TIERS = {
    "ai_prediction": {"BANK"},
    "quantum_crypto": {"BANK"},
    "basic_topology": {"TRIAL", "COMMUNITY", "BANK"},
    "alerts": {"COMMUNITY", "BANK"},
    "priority_support": {"BANK"},
}


class LicenseTier(str, enum.Enum):
    TRIAL = "TRIAL"
    COMMUNITY = "COMMUNITY"
    BANK = "BANK"


class LicenseManager:
    """License lifecycle management."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Activation ──────────────────────────────────────────────────────

    def activate_license(self, key: str) -> "models.License":  # type: ignore[name-defined]
        from models import License, LicenseTierEnum

        try:
            uuid.UUID(key, version=4)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_KEY_FORMAT", "message": "License key must be a valid UUID v4."},
            )

        existing = self.db.query(License).filter(License.key == key).first()
        if existing and existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "KEY_ALREADY_ACTIVE", "message": "This license key is already active."},
            )

        # Determine tier from key prefix convention (first segment)
        tier = self._resolve_tier_from_key(key)
        now = datetime.datetime.utcnow()
        expires_at: Optional[datetime.datetime] = None
        max_devices: Optional[int] = TIER_DEVICE_LIMITS.get(tier.value)

        if tier == LicenseTier.TRIAL:
            expires_at = now + datetime.timedelta(days=TRIAL_DURATION_DAYS)

        if existing:
            existing.tier = tier.value
            existing.activated_at = now
            existing.expires_at = expires_at
            existing.max_devices = max_devices
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            return existing

        license_record = License(
            key=key,
            tier=tier.value,
            activated_at=now,
            expires_at=expires_at,
            max_devices=max_devices,
            is_active=True,
        )
        self.db.add(license_record)
        self.db.commit()
        self.db.refresh(license_record)
        logger.info("License activated: key=%s tier=%s", key, tier.value)
        return license_record

    # ─── Status ──────────────────────────────────────────────────────────

    def get_current_tier(self) -> LicenseTier:
        """Return the active license tier (defaults to TRIAL if none found)."""
        from models import License

        license_record = (
            self.db.query(License).filter(License.is_active == True).first()  # noqa: E712
        )
        if license_record is None:
            return LicenseTier.TRIAL

        if license_record.expires_at and license_record.expires_at < datetime.datetime.utcnow():
            # Auto-expire: mark inactive and return TRIAL
            license_record.is_active = False
            self.db.commit()
            logger.info("License %s has expired; reverting to TRIAL.", license_record.key)
            return LicenseTier.TRIAL

        return LicenseTier(license_record.tier)

    def get_license_status(self) -> dict:
        from models import License

        license_record = (
            self.db.query(License).filter(License.is_active == True).first()  # noqa: E712
        )
        if license_record is None:
            return {
                "tier": LicenseTier.TRIAL.value,
                "is_active": False,
                "expires_at": None,
                "max_devices": TIER_DEVICE_LIMITS["TRIAL"],
                "days_remaining": None,
            }

        days_remaining: Optional[int] = None
        if license_record.expires_at:
            delta = license_record.expires_at - datetime.datetime.utcnow()
            days_remaining = max(0, delta.days)

        return {
            "tier": license_record.tier,
            "is_active": license_record.is_active,
            "expires_at": license_record.expires_at,
            "max_devices": license_record.max_devices,
            "days_remaining": days_remaining,
        }

    # ─── Enforcement ─────────────────────────────────────────────────────

    def check_feature_access(self, feature: str) -> None:
        """Raise HTTP 403 if the current tier cannot access *feature*."""
        allowed_tiers = _FEATURE_TIERS.get(feature, set())
        current_tier = self.get_current_tier()
        if current_tier.value not in allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FEATURE_NOT_AVAILABLE",
                    "message": f"Feature '{feature}' requires one of {sorted(allowed_tiers)}. Current tier: {current_tier.value}.",
                },
            )

    def check_device_limit(self, current_count: int) -> None:
        """Raise HTTP 403 if *current_count* exceeds the tier's device cap."""
        tier = self.get_current_tier()
        limit = TIER_DEVICE_LIMITS.get(tier.value)
        if limit is not None and current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "DEVICE_LIMIT_REACHED",
                    "message": f"Your {tier.value} tier allows a maximum of {limit} devices.",
                },
            )

    # ─── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_tier_from_key(key: str) -> LicenseTier:
        """Derive tier from the first segment of the UUID key.

        Convention (hex value of first segment mod 3):
          0 → TRIAL, 1 → COMMUNITY, 2 → BANK
        This is only a simulation convention for demo purposes.
        """
        first_segment = key.split("-")[0]
        idx = int(first_segment, 16) % 3
        return [LicenseTier.TRIAL, LicenseTier.COMMUNITY, LicenseTier.BANK][idx]


# ─── FastAPI dependency ───────────────────────────────────────────────────────

def get_license_manager(db: Session = Depends(get_db)) -> LicenseManager:
    return LicenseManager(db)


def require_feature(feature: str) -> Callable:
    """Dependency factory: raises 403 if current tier lacks *feature*."""

    def dependency(lm: LicenseManager = Depends(get_license_manager)) -> None:
        lm.check_feature_access(feature)

    return dependency
