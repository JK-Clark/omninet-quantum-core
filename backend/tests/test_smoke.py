# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# backend/tests/test_smoke.py — Smoke / integration tests for OmniNet Quantum-Core API

import os

# Use an in-memory SQLite database so tests run without a PostgreSQL server
# and leave no artifacts on disk.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-smoke-tests-only-not-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Patch the database engine before importing the app so that all modules share
# the same in-memory SQLite instance (StaticPool keeps a single connection).
import database

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)
database.engine = _TEST_ENGINE
database.SessionLocal = _TestSessionLocal

from main import app
from database import get_db

DEFAULT_EMAIL = "admin@omninet.local"
DEFAULT_PASSWORD = "OmniNet2026!"


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session")
def client():
    """Session-scoped TestClient; startup/shutdown events run once."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client):
    """Return a valid JWT for the default admin account."""
    response = client.post(
        "/api/auth/login",
        data={"username": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_returns_200_and_status_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_login_bad_credentials_returns_401(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_valid_credentials_returns_200_with_token(client):
    response = client.post(
        "/api/auth/login",
        data={"username": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


# ── Devices ───────────────────────────────────────────────────────────────────

def test_list_devices_without_token_returns_401(client):
    response = client.get("/api/devices")
    assert response.status_code == 401


# ── License ───────────────────────────────────────────────────────────────────

def test_license_status_with_valid_token_returns_200(client, auth_token):
    response = client.get(
        "/api/license/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "tier" in body
    assert "is_active" in body
