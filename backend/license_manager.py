# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/license_manager.py — License tier logic for OmniNet Quantum-Core

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas

logger = logging.getLogger(__name__)

LICENSE_SECRET = os.getenv("LICENSE_SECRET", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if not LICENSE_SECRET:
    logger.warning(
        "LICENSE_SECRET is not set via environment variable. "
        "HMAC license verification will be disabled. Set LICENSE_SECRET in production."
    )

# Legacy test keys available in development mode only
_DEFAULT_LEGACY_KEYS = "TRIAL-OMNINET-2026,COMMUNITY-GENIO-ELITE,BANK-QUANTUM-SECURE"
_LEGACY_KEYS_RAW = os.getenv("LEGACY_LICENSE_KEYS", _DEFAULT_LEGACY_KEYS)

_LEGACY_VALID_KEYS = {
    "TRIAL-OMNINET-2026": ("trial", 10),
    "COMMUNITY-GENIO-ELITE": ("community", None),
    "BANK-QUANTUM-SECURE": ("bank", None),
}

TIER_DURATIONS = {
    "trial": timedelta(days=7),
    "community": None,  # unlimited
    "bank": None,
}

VALID_TIERS = {"trial", "community", "bank"}


# ── HMAC key helpers ──────────────────────────────────────────────────────────

def _compute_integrity_hash(
    key: str,
    tier: str,
    expires_at: Optional[datetime],
    device_limit: Optional[int],
) -> str:
    """Compute SHA-256 integrity hash for a license DB record."""
    raw = "|".join([key, tier, str(expires_at), str(device_limit), LICENSE_SECRET])
    return hashlib.sha256(raw.encode()).hexdigest()


def _verify_hmac_key(key: str) -> Tuple[bool, Optional[str], Optional[datetime], Optional[int]]:
    """
    Verify an HMAC-signed license key.
    Format: TIER.EXPIRY_EPOCH.DEVICE_LIMIT.HMAC_SIGNATURE
    Returns: (is_valid, tier, expires_at, device_limit)
    """
    if not LICENSE_SECRET:
        return False, None, None, None

    parts = key.split(".")
    if len(parts) != 4:
        return False, None, None, None

    tier, expiry_epoch_str, device_limit_str, signature = parts

    if tier not in VALID_TIERS:
        return False, None, None, None

    message = f"{tier}.{expiry_epoch_str}.{device_limit_str}"
    expected_sig = hmac.new(
        LICENSE_SECRET.encode(),
        message.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        return False, None, None, None

    try:
        expiry_epoch = int(expiry_epoch_str)
        expires_at = datetime.utcfromtimestamp(expiry_epoch) if expiry_epoch > 0 else None
    except (ValueError, OSError):
        return False, None, None, None

    try:
        device_limit = int(device_limit_str) if device_limit_str != "0" else None
    except ValueError:
        return False, None, None, None

    return True, tier, expires_at, device_limit


def _validate_key(
    key: str,
) -> Tuple[Optional[str], Optional[datetime], Optional[int]]:
    """
    Validate a license key (HMAC-signed or legacy in development mode).
    Returns: (tier, expires_at, device_limit) on success, or (None, None, None) on failure.
    """
    # Try HMAC-signed key first
    is_valid, tier, expires_at, device_limit = _verify_hmac_key(key)
    if is_valid:
        return tier, expires_at, device_limit

    # Fall back to legacy keys in development mode only
    if ENVIRONMENT == "development":
        enabled_legacy = {k.strip() for k in _LEGACY_KEYS_RAW.split(",") if k.strip()}
        if key in enabled_legacy and key in _LEGACY_VALID_KEYS:
            legacy_tier, legacy_device_limit = _LEGACY_VALID_KEYS[key]
            duration = TIER_DURATIONS.get(legacy_tier)
            legacy_expires_at = datetime.utcnow() + duration if duration else None
            return legacy_tier, legacy_expires_at, legacy_device_limit

    return None, None, None


# ── Audit log ─────────────────────────────────────────────────────────────────

def _log_audit_event(
    db: Session,
    event: str,
    key: Optional[str] = None,
    tier: Optional[str] = None,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    """Write an audit log entry (key is stored as SHA-256 hash, never in plaintext)."""
    key_hash = hashlib.sha256(key.encode()).hexdigest() if key else None
    entry = models.LicenseAuditLog(
        event=event,
        license_key_hash=key_hash,
        tier=tier,
        user_id=user_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(entry)
    db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def get_license_status(db: Session) -> schemas.LicenseStatus:
    """Return the active license, verifying integrity. Downgrades to trial if tampered."""
    license_row = db.query(models.License).filter(models.License.is_active == True).first()

    if license_row is None:
        return schemas.LicenseStatus(
            tier="trial",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=7),
            device_limit=10,
        )

    # Integrity check — detect direct DB modifications
    if license_row.integrity_hash and LICENSE_SECRET:
        expected = _compute_integrity_hash(
            license_row.key,
            license_row.tier,
            license_row.expires_at,
            license_row.device_limit,
        )
        if not hmac.compare_digest(expected, license_row.integrity_hash):
            key_hash = hashlib.sha256(license_row.key.encode()).hexdigest()
            logger.critical(
                "TAMPER DETECTED: License record (key_hash=%s) has been modified! "
                "Forcing downgrade to trial.",
                key_hash,
            )
            _log_audit_event(
                db,
                event="tamper_detected",
                key=license_row.key,
                tier=license_row.tier,
                details="Integrity hash mismatch — forced downgrade to trial",
            )
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


def activate_license(
    key: str,
    user_id: int,
    db: Session,
    ip_address: Optional[str] = None,
) -> schemas.LicenseStatus:
    """Validate and activate a license key."""
    tier, expires_at, device_limit = _validate_key(key)

    if tier is None:
        _log_audit_event(
            db,
            event="access_denied",
            key=key,
            user_id=user_id,
            ip_address=ip_address,
            details="Invalid license key presented",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid license key",
        )

    # Deactivate any existing active license
    existing_active = db.query(models.License).filter(models.License.is_active == True).first()
    if existing_active:
        existing_active.is_active = False
        _log_audit_event(
            db,
            event="deactivated",
            key=existing_active.key,
            tier=existing_active.tier,
            user_id=user_id,
            ip_address=ip_address,
            details="Deactivated by new license activation",
        )
        db.flush()

    integrity_hash = _compute_integrity_hash(key, tier, expires_at, device_limit) if LICENSE_SECRET else None

    # Upsert the license record
    existing = db.query(models.License).filter(models.License.key == key).first()
    if existing:
        existing.is_active = True
        existing.tier = tier
        existing.expires_at = expires_at
        existing.device_limit = device_limit
        existing.activated_by = user_id
        existing.activated_at = datetime.utcnow()
        existing.integrity_hash = integrity_hash
        db.flush()
    else:
        new_license = models.License(
            key=key,
            tier=tier,
            is_active=True,
            expires_at=expires_at,
            device_limit=device_limit,
            activated_by=user_id,
            activated_at=datetime.utcnow(),
            integrity_hash=integrity_hash,
        )
        db.add(new_license)
        db.flush()

    db.commit()

    _log_audit_event(
        db,
        event="activated",
        key=key,
        tier=tier,
        user_id=user_id,
        ip_address=ip_address,
        details=f"License activated: tier={tier}",
    )

    return get_license_status(db)


def ensure_default_license(db: Session) -> None:
    """Insert a trial license if no license exists in the database."""
    if db.query(models.License).count() == 0:
        key = "TRIAL-OMNINET-2026"
        tier = "trial"
        device_limit = 10
        expires_at = datetime.utcnow() + timedelta(days=7)
        integrity_hash = _compute_integrity_hash(key, tier, expires_at, device_limit) if LICENSE_SECRET else None
        trial = models.License(
            key=key,
            tier=tier,
            is_active=True,
            expires_at=expires_at,
            device_limit=device_limit,
            integrity_hash=integrity_hash,
        )
        db.add(trial)
        db.commit()

