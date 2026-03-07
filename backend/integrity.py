# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
OmniNet Quantum-Core — Software Integrity Verification Module.

Computes SHA-256 checksums of critical backend files at startup and compares
them against a signed manifest (``integrity_manifest.json``) that is generated
by the secure deployment script (``deploy_secure.sh``).

If a protected file has been tampered with the process exits immediately with
``"System Integrity Violated — Security Lockdown"`` — preventing any further
operation until the authorised software is restored.

Manifest lifecycle
------------------
1. ``deploy_secure.sh`` calls ``generate_manifest()`` after copying the
   pristine files into the Docker build context but *before* any obfuscation.
2. The resulting ``integrity_manifest.json`` is baked into the image.
3. At every startup ``verify_integrity()`` re-hashes the live files and
   compares against the manifest.

Development / CI mode
---------------------
When ``integrity_manifest.json`` does not exist the function logs a warning
and **continues** without halting.  This allows development and testing without
requiring a full secure-deployment cycle.  In production the manifest is always
present and verification is mandatory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

# Directory that contains this file (backend/)
_BACKEND_DIR = Path(__file__).resolve().parent

# Files whose integrity is verified at startup.
# Additional files can be added; the manifest must be regenerated afterward.
PROTECTED_FILES: tuple[str, ...] = (
    "license_manager.py",
    "quantum_engine.py",
)

# Path to the manifest produced by deploy_secure.sh
MANIFEST_PATH: Path = _BACKEND_DIR / "integrity_manifest.json"

# gitignore note: integrity_manifest.json is generated at deploy time and
# should NOT be committed to the repository.


# ─── Hash utilities ───────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_manifest(output_path: Optional[Path] = None) -> Dict[str, str]:
    """Compute SHA-256 of all :data:`PROTECTED_FILES` and write the manifest.

    This function is called by ``deploy_secure.sh`` during the secure build
    process.  It must be run *before* any obfuscation that modifies the files.

    Args:
        output_path: Where to write the JSON manifest.  Defaults to
            :data:`MANIFEST_PATH`.

    Returns:
        A ``{filename: sha256_hex}`` dict that was written to disk.
    """
    output_path = output_path or MANIFEST_PATH
    manifest: Dict[str, str] = {}

    for fname in PROTECTED_FILES:
        fpath = _BACKEND_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(
                f"[Integrity] Cannot generate manifest — file not found: {fpath}"
            )
        digest = sha256_file(fpath)
        manifest[fname] = digest
        logger.info("[Integrity] %s  SHA-256: %s", fname, digest)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    logger.info("[Integrity] Manifest written to %s", output_path)
    return manifest


def verify_integrity() -> None:
    """Verify that all protected files match the deployment manifest.

    Behaviour
    ---------
    * **Manifest absent** (development / CI): logs a ``WARNING`` and returns
      without halting.  This allows the server to run without a secure-deploy
      cycle.
    * **Manifest present, hashes match**: logs ``INFO`` confirmation for each
      file.
    * **Manifest present, hash mismatch**: logs a ``CRITICAL`` error then calls
      ``sys.exit(1)`` with the message
      ``"System Integrity Violated — Security Lockdown"``.
    * **Protected file missing**: treated as a tampering event — same exit
      behaviour as a hash mismatch.

    Raises:
        SystemExit(1): On any integrity violation when the manifest is present.
    """
    if not MANIFEST_PATH.exists():
        logger.warning(
            "[Integrity] Manifest not found at %s — skipping integrity check "
            "(development mode).  Run deploy_secure.sh to enable production "
            "integrity enforcement.",
            MANIFEST_PATH,
        )
        return

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            manifest: Dict[str, str] = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        _lockdown(f"Cannot read integrity manifest: {exc}")

    violations: list[str] = []

    for fname, expected_digest in manifest.items():
        fpath = _BACKEND_DIR / fname
        if not fpath.exists():
            violations.append(f"MISSING: {fname}")
            continue
        actual_digest = sha256_file(fpath)
        if actual_digest != expected_digest:
            violations.append(
                f"TAMPERED: {fname} (expected {expected_digest[:16]}…, "
                f"got {actual_digest[:16]}…)"
            )
        else:
            logger.info("[Integrity] ✓  %s  SHA-256 verified", fname)

    if violations:
        detail = "; ".join(violations)
        _lockdown(f"Integrity violations detected — {detail}")


def _lockdown(reason: str) -> None:
    """Log a critical error and terminate the process."""
    msg = "System Integrity Violated — Security Lockdown"
    logger.critical("[Integrity] %s | Reason: %s", msg, reason)
    # Print directly to stderr so the message is visible even if logging
    # is not fully initialised.
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"  SECURITY ALERT: {msg}", file=sys.stderr)
    print(f"  {reason}", file=sys.stderr)
    print(f"  Contact Genio Elite support: support@genioelite.io", file=sys.stderr)
    print(f"{'='*70}\n", file=sys.stderr)
    sys.exit(1)
