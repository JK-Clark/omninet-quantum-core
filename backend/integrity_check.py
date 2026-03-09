# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/integrity_check.py — Runtime integrity verification for OmniNet Quantum-Core

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Critical files to verify at startup
CRITICAL_FILES = [
    "license_manager.py",
    "auth.py",
    "models.py",
    "main.py",
    "quantum_engine.py",
]


def compute_file_hash(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_manifest(manifest_path: Path) -> Dict[str, str]:
    if not manifest_path.exists():
        return {}
    with open(manifest_path) as f:
        return json.load(f)


def generate_manifest(app_dir: Path, manifest_path: Path) -> Dict[str, str]:
    """Generate and save a fresh integrity manifest for all critical files."""
    manifest = {}
    for filename in CRITICAL_FILES:
        filepath = app_dir / filename
        if filepath.exists():
            manifest[filename] = compute_file_hash(filepath)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Integrity manifest generated at %s", manifest_path)
    return manifest


def verify_integrity(app_dir: Path, manifest_path: Path) -> List[str]:
    """
    Verify critical files against the manifest.
    Returns list of tampered/missing filenames (empty = all OK).
    """
    manifest = load_manifest(manifest_path)
    if not manifest:
        logger.warning("No integrity manifest found at %s — skipping verification", manifest_path)
        return []

    tampered = []
    for filename, expected_hash in manifest.items():
        filepath = app_dir / filename
        if not filepath.exists():
            logger.critical("INTEGRITY VIOLATION: %s is missing!", filename)
            tampered.append(filename)
            continue
        actual_hash = compute_file_hash(filepath)
        if actual_hash != expected_hash:
            logger.critical(
                "INTEGRITY VIOLATION: %s has been modified! Expected=%s Got=%s",
                filename,
                expected_hash,
                actual_hash,
            )
            tampered.append(filename)

    if not tampered:
        logger.info("Integrity check passed — all %d critical files verified.", len(manifest))
    return tampered
