# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/main.py — OmniNet Quantum-Core FastAPI Application

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

import ai_predictor
import audit
import auth
import hmac as _hmac
import integrity_check
import license_manager
import models
import network_drivers
import reports
import schemas
from database import create_tables, get_db

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniNet Quantum-Core API", version="1.0.0")

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:3000,http://localhost:80")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics ────────────────────────────────────────────────────────
if PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app)


# ── Dependencies ──────────────────────────────────────────────────────────────
def require_admin(current_user: models.User = Depends(auth.get_current_user)) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_bank_license(db: Session = Depends(get_db)) -> None:
    lic = license_manager.get_license_status(db)
    if lic.tier != "bank" or not lic.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank license required for AI features",
        )


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    create_tables()
    db = next(get_db())
    try:
        auth.ensure_default_admin(db)
        license_manager.ensure_default_license(db)
        network_drivers.ensure_demo_devices(db)
        ai_predictor.ensure_demo_predictions(db)
    finally:
        db.close()

    # File integrity check — alert only, do not block startup
    app_dir = Path(__file__).parent
    manifest_path = app_dir / "integrity_manifest.json"
    tampered = integrity_check.verify_integrity(app_dir, manifest_path)
    if tampered:
        logger.critical(
            "STARTUP INTEGRITY WARNING: The following critical files have been modified: %s",
            tampered,
        )


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=schemas.HealthResponse, tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login", response_model=schemas.Token, tags=["Auth"])
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    audit.log_action(
        db,
        action="user.login",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(user),
    )


@app.post("/api/auth/register", response_model=schemas.UserResponse, tags=["Auth"])
async def register(
    user_create: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    existing = auth.get_user_by_email(db, user_create.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = models.User(
        email=user_create.email,
        hashed_password=auth.hash_password(user_create.password),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/auth/me", response_model=schemas.UserResponse, tags=["Auth"])
async def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ── License ───────────────────────────────────────────────────────────────────
@app.get("/api/license/status", response_model=schemas.LicenseStatus, tags=["License"])
async def get_license_status(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return license_manager.get_license_status(db)


@app.post("/api/license/activate", response_model=schemas.LicenseStatus, tags=["License"])
@limiter.limit("5/minute")
async def activate_license(
    request: Request,
    payload: schemas.LicenseActivate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else None
    return license_manager.activate_license(payload.key, current_user.id, db, ip_address=ip_address)


@app.get("/api/license/audit", response_model=schemas.LicenseAuditResponse, tags=["License"])
async def get_license_audit(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    entries = (
        db.query(models.LicenseAuditLog)
        .order_by(models.LicenseAuditLog.created_at.desc())
        .all()
    )
    return schemas.LicenseAuditResponse(
        entries=[schemas.LicenseAuditEntry.model_validate(e) for e in entries],
        total=len(entries),
    )


@app.get("/api/license/verify-integrity", tags=["License"])
async def verify_license_integrity(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Check integrity hashes for all license records and return a report."""
    licenses = db.query(models.License).all()
    report = []
    for lic in licenses:
        if not lic.integrity_hash or not license_manager.LICENSE_SECRET:
            report.append({
                "id": lic.id,
                "tier": lic.tier,
                "is_active": lic.is_active,
                "integrity": "unchecked",
                "reason": "No integrity hash or LICENSE_SECRET not configured",
            })
            continue
        expected = license_manager._compute_integrity_hash(
            lic.key, lic.tier, lic.expires_at, lic.device_limit
        )
        ok = _hmac.compare_digest(expected, lic.integrity_hash)
        report.append({
            "id": lic.id,
            "tier": lic.tier,
            "is_active": lic.is_active,
            "integrity": "ok" if ok else "TAMPERED",
        })
    return {"licenses": report, "total": len(report)}


# ── Devices ───────────────────────────────────────────────────────────────────
@app.get("/api/devices", response_model=List[schemas.DeviceResponse], tags=["Devices"])
async def list_devices(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Device).all()


@app.post("/api/devices", response_model=schemas.DeviceResponse, tags=["Devices"])
async def create_device(
    payload: schemas.DeviceCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    device = models.Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    audit.log_action(
        db,
        action="device.created",
        user_id=current_user.id,
        resource_type="device",
        resource_id=device.id,
    )
    return device


@app.get("/api/devices/alerts", response_model=List[schemas.AlertResponse], tags=["Devices"])
async def get_alerts(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Alert)
        .filter(models.Alert.is_resolved == False)
        .order_by(models.Alert.created_at.desc())
        .all()
    )


@app.post("/api/devices/discover", response_model=List[schemas.DeviceResponse], tags=["Devices"])
async def discover_devices(
    payload: schemas.DiscoverRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        discovered = network_drivers.discover_devices(
            cidr=payload.cidr,
            username=payload.username,
            password=payload.password,
            device_type=payload.device_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    added = []
    for dev in discovered:
        existing = db.query(models.Device).filter(models.Device.ip_address == dev.ip_address).first()
        if not existing:
            obj = models.Device(**dev.model_dump())
            db.add(obj)
            db.flush()
            added.append(obj)

    db.commit()
    for obj in added:
        db.refresh(obj)

    return db.query(models.Device).all()


# ── Topology ──────────────────────────────────────────────────────────────────
@app.get("/api/topology", response_model=schemas.TopologyResponse, tags=["Topology"])
async def get_topology(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return network_drivers.get_topology(db)


# ── AI Predictions (Bank license required) ────────────────────────────────────
@app.get("/api/ai/predictions", response_model=List[schemas.AIpredictionResponse], tags=["AI"])
async def get_all_predictions(
    current_user: models.User = Depends(auth.get_current_user),
    _bank: None = Depends(require_bank_license),
    db: Session = Depends(get_db),
):
    predictions = db.query(models.AIprediction).all()
    if not predictions:
        ai_predictor.generate_predictions_all(db)
        predictions = db.query(models.AIprediction).all()
    return predictions


@app.get("/api/ai/predictions/{device_id}", response_model=schemas.AIpredictionResponse, tags=["AI"])
async def get_device_prediction(
    device_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    _bank: None = Depends(require_bank_license),
    db: Session = Depends(get_db),
):
    try:
        prediction = ai_predictor.predict_device_health(device_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return prediction


# ── Reports ───────────────────────────────────────────────────────────────────
@app.get("/api/reports/generate", tags=["Reports"])
async def generate_report(
    device_id: int = Query(..., description="Device ID to generate the report for"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return reports.generate_device_report(device_id, db)


# ── Audit Logs ────────────────────────────────────────────────────────────────
@app.get("/api/audit/logs", tags=["Audit"])
async def get_audit_logs(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return the 100 most recent audit log entries (admin only)."""
    logs = audit.get_recent_logs(db, limit=100)
    return [
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "ip_address": entry.ip_address,
            "details": entry.details,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in logs
    ]


# ── WebSocket — real-time topology ───────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()


@app.websocket("/ws/topology")
async def websocket_topology(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    try:
        while True:
            topology = network_drivers.get_topology(db)
            payload = topology.model_dump()
            # Serialize datetime objects
            await websocket.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

