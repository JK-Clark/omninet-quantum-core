# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
License management: hardware-locked tier validation, Ed25519 signature
verification, mandatory-expiry enforcement, anti-fraud clock-rollback
detection, and feature gating.

Key format
----------
  OMNI-<base64url(payload_json)>.<signature_hex>

  ``payload_json`` is compact UTF-8 JSON with **sorted keys**, for example::

      {"exp":"2027-06-01T00:00:00","hw":"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4","tier":"BANK"}

  The 64-byte Ed25519 signature is computed over the *raw payload bytes*
  (``payload_json`` encoded as UTF-8) using the issuer's private signing key.
  The embedded public verify key is used here for verification; only the
  issuer's private key — never committed to this repository — can produce
  valid signatures.

  Every license key **must** carry a non-null ``exp`` value.  Perpetual
  (non-expiring) licenses are not supported by this business model.

Anti-fraud clock-rollback detection
------------------------------------
  On every successful tier evaluation the current UTC timestamp is persisted
  to the ``License.last_checked_at`` column.  On the following evaluation, if
  the system clock reports a time more than :data:`_ROLLBACK_TOLERANCE` before
  ``last_checked_at`` a clock-rollback is inferred and the system immediately
  falls back to TRIAL without updating the stored timestamp.  The "future"
  value in ``last_checked_at`` continues to detect rollback on subsequent calls.
"""

import base64
import datetime
import enum
import hashlib
import json
import logging
import platform
import sys
import uuid
from typing import Callable, Optional, Tuple

import nacl.exceptions
import nacl.signing
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

# ─── Public verify key (no secret material here) ──────────────────────────────
# This is the Ed25519 *public* key used to verify license signatures.
# The matching private signing key is held exclusively by the issuer and is
# NEVER committed to this repository.  Even with full access to this source
# code an attacker cannot forge a valid license key without the private key.
_PUBLIC_KEY_HEX = "50e2d4307b40df4891ed8b80c49485d0774c1c2cac09e1363a88ac4bf51445f6"

# ─── Constants ────────────────────────────────────────────────────────────────

# Days until a TRIAL license expires from the moment it is first activated
TRIAL_DURATION_DAYS = 7

# Device limits per tier (None = unlimited)
TIER_DEVICE_LIMITS: dict[str, Optional[int]] = {
    "TRIAL": 10,
    "COMMUNITY": None,
    "BANK": None,
}

# Features and the tiers that are permitted to use them
_FEATURE_TIERS: dict[str, set[str]] = {
    "ai_prediction": {"BANK"},
    "quantum_crypto": {"BANK"},
    "basic_topology": {"TRIAL", "COMMUNITY", "BANK"},
    "alerts": {"COMMUNITY", "BANK"},
    "priority_support": {"BANK"},
}

# Tolerance window used when comparing utcnow() against last_checked_at for
# fine-grained clock-rollback detection.  5 minutes covers normal NTP
# micro-adjustments without allowing meaningful time-travel fraud.
_ROLLBACK_TOLERANCE = datetime.timedelta(minutes=5)

# Coarse safety net: if utcnow() is more than this far before activated_at we
# treat the license as invalid (catches gross clock resets at activation time).
_MAX_CLOCK_SKEW = datetime.timedelta(hours=24)

# All OmniNet license keys begin with this sentinel prefix
_KEY_PREFIX = "OMNI-"


class LicenseTier(str, enum.Enum):
    TRIAL = "TRIAL"
    COMMUNITY = "COMMUNITY"
    BANK = "BANK"


# ─── Hardware fingerprinting ──────────────────────────────────────────────────

def get_hardware_id() -> str:
    """Return a stable 32-character hardware fingerprint for this server.

    The fingerprint is a truncated SHA-256 digest combining:

    * The primary network interface MAC address (via :func:`uuid.getnode`).
    * The CPU model string from ``/proc/cpuinfo`` on Linux, or from
      :func:`platform.processor` on other operating systems.

    .. note::
        In Docker deployments the MAC address is assigned by the container
        runtime and changes on every restart unless pinned.  Set a fixed
        ``mac_address`` for the backend service in ``docker-compose.yml`` to
        keep the fingerprint stable across restarts::

            services:
              backend:
                mac_address: "02:42:ac:11:00:02"
    """
    mac = uuid.getnode()
    mac_str = f"{mac:012x}"

    cpu_info: str = platform.processor() or platform.machine() or "unknown"
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        cpu_info = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    raw = f"{mac_str}|{cpu_info}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ─── License key parsing & Ed25519 verification ───────────────────────────────

def _b64url_decode(s: str) -> bytes:
    """Decode a URL-safe base64 string with or without ``=`` padding."""
    s = s.replace("-", "+").replace("_", "/")
    pad = (4 - len(s) % 4) % 4
    return base64.b64decode(s + "=" * pad)


def parse_and_verify_license_key(
    key: str, hardware_id: str
) -> Tuple[LicenseTier, datetime.datetime]:
    """Parse *key*, verify its Ed25519 signature, and validate the hardware ID.

    Args:
        key: The full license key string (``OMNI-<payload>.<sig>``).
        hardware_id: The 32-character fingerprint of the current server
            (from :func:`get_hardware_id`).

    Returns:
        ``(tier, expires_at)`` — ``expires_at`` is always a concrete datetime;
        perpetual (null-expiry) licenses are rejected.

    Raises:
        :class:`~fastapi.HTTPException` ``400`` — malformed or perpetual key.
        :class:`~fastapi.HTTPException` ``402`` — key has expired.
        :class:`~fastapi.HTTPException` ``403`` — invalid signature or
            hardware ID mismatch (system remains in TRIAL).
    """
    if not key.startswith(_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_KEY_FORMAT",
                "message": f"License key must start with '{_KEY_PREFIX}'.",
            },
        )

    inner = key[len(_KEY_PREFIX):]
    parts = inner.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_KEY_FORMAT", "message": "Malformed license key structure."},
        )

    payload_b64, sig_hex = parts

    # ── Decode payload ────────────────────────────────────────────────
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_KEY_FORMAT", "message": "Cannot decode license payload."},
        )

    # ── Ed25519 signature verification ───────────────────────────────
    try:
        sig_bytes = bytes.fromhex(sig_hex)
        vk = nacl.signing.VerifyKey(bytes.fromhex(_PUBLIC_KEY_HEX))
        vk.verify(payload_bytes, sig_bytes)
    except (nacl.exceptions.BadSignatureError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "INVALID_SIGNATURE",
                "message": "License signature is invalid.  The system remains in TRIAL mode.",
            },
        )

    # ── Required payload fields ───────────────────────────────────────
    for field in ("hw", "tier", "exp"):
        if field not in payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_KEY_FORMAT", "message": f"Missing payload field: '{field}'."},
            )

    # ── Hardware ID binding ───────────────────────────────────────────
    if payload["hw"] != hardware_id:
        logger.warning(
            "License hardware ID mismatch: key_hw=%s server_hw=%s",
            payload["hw"],
            hardware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "HARDWARE_MISMATCH",
                "message": (
                    "This license was issued for a different server.  "
                    "The system remains in TRIAL mode."
                ),
            },
        )

    # ── Tier ──────────────────────────────────────────────────────────
    try:
        tier = LicenseTier(payload["tier"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_TIER", "message": f"Unknown tier: '{payload['tier']}'."},
        )

    # ── Expiry (mandatory — perpetual licenses are not permitted) ────────
    if payload["exp"] is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "MISSING_EXPIRY",
                "message": "Toutes les licences doivent comporter une date d'expiration.",
            },
        )
    if not isinstance(payload["exp"], str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_KEY_FORMAT", "message": "Expiry date must be an ISO-8601 string."},
        )
    try:
        expires_at: datetime.datetime = datetime.datetime.fromisoformat(payload["exp"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_KEY_FORMAT", "message": "Malformed expiry date in license."},
        )
    if expires_at < datetime.datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error_code": "LICENSE_EXPIRED",
                "message": (
                    "Votre licence a expiré. "
                    "Contactez Genio Elite pour le renouvellement."
                ),
            },
        )

    return tier, expires_at


# ─── License manager ──────────────────────────────────────────────────────────

class LicenseManager:
    """License lifecycle management with hardware-locked Ed25519 verification."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Activation ──────────────────────────────────────────────────────

    def activate_license(self, key: str) -> "models.License":  # type: ignore[name-defined]
        from models import License

        hw_id = get_hardware_id()
        tier, expires_at = parse_and_verify_license_key(key, hw_id)

        max_devices: Optional[int] = TIER_DEVICE_LIMITS.get(tier.value)
        now = datetime.datetime.utcnow()

        existing = self.db.query(License).filter(License.key == key).first()
        if existing and existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "KEY_ALREADY_ACTIVE", "message": "This license key is already active."},
            )

        if existing:
            existing.tier = tier.value
            existing.activated_at = now
            existing.expires_at = expires_at
            existing.max_devices = max_devices
            existing.hardware_id = hw_id
            existing.last_checked_at = now
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            logger.info("License re-activated: key=%.20s tier=%s hw=%s", key, tier.value, hw_id)
            return existing

        license_record = License(
            key=key,
            tier=tier.value,
            activated_at=now,
            expires_at=expires_at,
            max_devices=max_devices,
            hardware_id=hw_id,
            last_checked_at=now,
            is_active=True,
        )
        self.db.add(license_record)
        self.db.commit()
        self.db.refresh(license_record)
        logger.info("License activated: key=%.20s tier=%s hw=%s", key, tier.value, hw_id)
        return license_record

    # ─── Status ──────────────────────────────────────────────────────────

    def get_current_tier(self) -> LicenseTier:
        """Return the active license tier (defaults to TRIAL if none found).

        Applies four runtime checks on every call:

        1. **Fine-grained clock-rollback detection** (``last_checked_at``) —
           the most recent successful evaluation timestamp is persisted in the
           database.  If the system clock now reads more than
           :data:`_ROLLBACK_TOLERANCE` (5 min) before that timestamp, a
           rollback is inferred.  ``last_checked_at`` is intentionally *not*
           updated on rollback detection so the "future" value continues to
           flag subsequent calls.
        2. **Coarse clock-rollback safety net** (``activated_at``) — catches
           gross clock resets that occurred before the first evaluation.
        3. **Expiry check** — if ``expires_at`` has passed, the license is
           marked inactive and the system falls back to TRIAL with the
           localised renewal message.
        4. **Hardware ID re-validation** — if the current server fingerprint
           no longer matches the one recorded at activation the system falls
           back to TRIAL without marking the licence inactive (so the original
           server can still use it).
        """
        from models import License

        license_record = (
            self.db.query(License).filter(License.is_active == True).first()  # noqa: E712
        )
        if license_record is None:
            return LicenseTier.TRIAL

        now = datetime.datetime.utcnow()

        # ── 1. Fine-grained rollback detection via last_checked_at ────────────
        if (
            license_record.last_checked_at is not None
            and now < license_record.last_checked_at - _ROLLBACK_TOLERANCE
        ):
            logger.warning(
                "Clock rollback detected via last_checked_at "
                "(now=%s, last_checked_at=%s, tolerance=%s). Reverting to TRIAL.",
                now.isoformat(),
                license_record.last_checked_at.isoformat(),
                _ROLLBACK_TOLERANCE,
            )
            # Do NOT update last_checked_at — keep the "future" value so
            # subsequent calls continue to detect the rollback.
            return LicenseTier.TRIAL

        # ── 2. Coarse rollback safety net via activated_at ────────────────────
        if (
            license_record.activated_at is not None
            and now < license_record.activated_at - _MAX_CLOCK_SKEW
        ):
            logger.warning(
                "Gross clock rollback detected via activated_at "
                "(now=%s, activated_at=%s). Reverting to TRIAL.",
                now.isoformat(),
                license_record.activated_at.isoformat(),
            )
            return LicenseTier.TRIAL

        # ── 3. Expiry check ───────────────────────────────────────────────────
        if license_record.expires_at is not None and license_record.expires_at < now:
            license_record.is_active = False
            self.db.commit()
            logger.info("License %.20s expired; reverting to TRIAL.", license_record.key)
            # The localised renewal message is surfaced via get_license_status();
            # here we simply return TRIAL.
            return LicenseTier.TRIAL

        # ── 4. Hardware ID re-validation ──────────────────────────────────────
        if license_record.hardware_id and license_record.hardware_id != get_hardware_id():
            logger.warning(
                "Hardware ID mismatch at runtime (stored=%s). Reverting to TRIAL.",
                license_record.hardware_id,
            )
            return LicenseTier.TRIAL

        # ── All checks passed: persist the current timestamp ──────────────────
        license_record.last_checked_at = now
        self.db.commit()

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
                "message": None,
            }

        now = datetime.datetime.utcnow()
        days_remaining: Optional[int] = None
        message: Optional[str] = None

        if license_record.expires_at:
            delta = license_record.expires_at - now
            days_remaining = max(0, delta.days)
            if days_remaining == 0 and license_record.expires_at < now:
                message = (
                    "Votre licence a expiré. "
                    "Contactez Genio Elite pour le renouvellement."
                )
            elif days_remaining <= 30:
                message = (
                    f"Votre licence expire dans {days_remaining} jour(s). "
                    "Contactez Genio Elite pour le renouvellement."
                )

        return {
            "tier": license_record.tier,
            "is_active": license_record.is_active,
            "expires_at": license_record.expires_at,
            "max_devices": license_record.max_devices,
            "days_remaining": days_remaining,
            "message": message,
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
                    "message": (
                        f"Feature '{feature}' requires one of {sorted(allowed_tiers)}. "
                        f"Current tier: {current_tier.value}."
                    ),
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


# ─── FastAPI dependency ───────────────────────────────────────────────────────

def get_license_manager(db: Session = Depends(get_db)) -> LicenseManager:
    return LicenseManager(db)


def require_feature(feature: str) -> Callable:
    """Dependency factory: raises 403 if the current tier lacks *feature*."""

    def dependency(lm: LicenseManager = Depends(get_license_manager)) -> None:
        lm.check_feature_access(feature)

    return dependency
