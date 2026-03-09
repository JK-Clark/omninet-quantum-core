# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/tests/test_smoke.py — Smoke/integration tests for OmniNet Quantum-Core API

"""
Smoke Tests
===========
Basic integration tests that verify the API endpoints are reachable and return
the expected HTTP status codes.  These tests use an in-memory SQLite database
so that no external Postgres instance is required.
"""

import os

# Must be set before importing any application module so that database.py picks
# up the SQLite fallback instead of trying to connect to PostgreSQL.
os.environ.setdefault("USE_SQLITE_FALLBACK", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-DO-NOT-USE-IN-PRODUCTION-smoke-tests-only")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient that triggers the ASGI startup event."""
    with TestClient(app) as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_admin_token(client: TestClient) -> str:
    """Return a valid JWT token for the default admin account."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin@omninet.local",
            "password": "OmniNet2026!",
        },
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health_returns_ok(client):
    """GET /api/health should return 200 with status=ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_login_bad_credentials_returns_401(client):
    """POST /api/auth/login with wrong credentials should return 401."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "nobody@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


def test_login_good_credentials_returns_token(client):
    """POST /api/auth/login with correct admin credentials should return 200 + JWT."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin@omninet.local",
            "password": "OmniNet2026!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_devices_without_token_returns_401(client):
    """GET /api/devices without Authorization header should return 401."""
    response = client.get("/api/devices")
    assert response.status_code == 401


def test_license_status_with_valid_token_returns_200(client):
    """GET /api/license/status with a valid token should return 200."""
    token = _get_admin_token(client)
    response = client.get(
        "/api/license/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tier" in data
    assert "is_active" in data

