# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# backend/tests/test_smoke.py — Smoke/integration tests for the OmniNet API

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force SQLite in-memory database for tests
os.environ.setdefault("USE_SQLITE_FALLBACK", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_omninet.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-smoke-tests-minimum-64-chars-padding-padding")

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db
from main import app

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


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_omninet.db"):
        os.remove("./test_omninet.db")


@pytest.fixture(scope="session")
def client(setup_database):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def auth_token(client):
    """Obtain a valid JWT token using the default admin credentials."""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@omninet.local", "password": "OmniNet2026!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ── Smoke tests ───────────────────────────────────────────────────────────────

def test_health_returns_200_and_ok(client):
    """GET /api/health → 200 + {"status": "ok"}"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_login_bad_credentials_returns_401(client):
    """POST /api/auth/login with wrong credentials → 401"""
    response = client.post(
        "/api/auth/login",
        data={"username": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_valid_credentials_returns_token(client):
    """POST /api/auth/login with valid admin credentials → 200 + JWT token"""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@omninet.local", "password": "OmniNet2026!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_devices_without_token_returns_401(client):
    """GET /api/devices without auth token → 401"""
    response = client.get("/api/devices")
    assert response.status_code == 401


def test_license_status_with_token_returns_200(client, auth_token):
    """GET /api/license/status with valid token → 200"""
    response = client.get(
        "/api/license/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
