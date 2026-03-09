# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/main.py — OmniNet Quantum-Core FastAPI Application

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import ai_predictor
import auth
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

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics ────────────────────────────────────────────────────────
if PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app)


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


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=schemas.HealthResponse, tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login", response_model=schemas.Token, tags=["Auth"])
async def login(
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
async def activate_license(
    payload: schemas.LicenseActivate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return license_manager.activate_license(payload.key, current_user.id, db)


# ── Devices ───────────────────────────────────────────────────────────────────
@app.get("/api/devices", response_model=List[schemas.DeviceResponse], tags=["Devices"])
async def list_devices(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Device).all()


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


# ── AI Predictions ────────────────────────────────────────────────────────────
@app.get("/api/ai/predictions", response_model=List[schemas.AIpredictionResponse], tags=["AI"])
async def get_all_predictions(
    current_user: models.User = Depends(auth.get_current_user),
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
