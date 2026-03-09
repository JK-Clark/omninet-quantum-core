# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/tests/test_smoke.py — Smoke / integration tests for OmniNet Quantum-Core API

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use an in-memory SQLite database for tests
os.environ.setdefault("USE_SQLITE_FALLBACK", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_omninet.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-smoke-tests-64-chars-minimum!!")
os.environ.setdefault("ENVIRONMENT", "test")

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


# ── Test database setup ───────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///./test_omninet.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    """Set up the test client with an in-memory SQLite database."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def auth_token(client):
    """Obtain a valid JWT token for the default admin user."""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@omninet.local", "password": "OmniNet2026!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ── Smoke tests ───────────────────────────────────────────────────────────────

def test_health_check(client):
    """GET /api/health → 200 + {"status": "ok"}"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_login_wrong_credentials(client):
    """POST /api/auth/login with wrong credentials → 401"""
    response = client.post(
        "/api/auth/login",
        data={"username": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_valid_credentials(client):
    """POST /api/auth/login with valid admin credentials → 200 + JWT token"""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@omninet.local", "password": "OmniNet2026!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data


def test_get_devices_without_token(client):
    """GET /api/devices without authentication → 401"""
    response = client.get("/api/devices")
    assert response.status_code == 401


def test_get_license_status_with_token(client, auth_token):
    """GET /api/license/status with valid token → 200"""
    response = client.get(
        "/api/license/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tier" in data
    assert "is_active" in data
