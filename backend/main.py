"""
OmniNet Quantum-Core — FastAPI application entrypoint.

Routes:
  POST   /api/auth/register
  POST   /api/auth/login
  POST   /api/auth/refresh

  GET    /api/devices
  POST   /api/devices
  GET    /api/devices/{id}
  DELETE /api/devices/{id}

  POST   /api/topology/discover
  GET    /api/topology/map

  POST   /api/ai/train/{device_id}
  GET    /api/ai/predict/{device_id}

  POST   /api/license/activate
  GET    /api/license/status

  WS     /ws/topology

  GET    /metrics  (Prometheus)
"""

import asyncio
import datetime
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from ai_predictor import FailurePredictor, get_predictor
from database import get_db, init_db, settings
from license_manager import LicenseManager, get_license_manager, require_feature
from models import Alert, Device, License, TopologyLink, User
from network_drivers import NetworkDiscoveryEngine
from quantum_engine import generate_keypair, get_quantum_keypair
from schemas import (
    APIError,
    APIResponse,
    DeviceCreate,
    DeviceOut,
    DiscoverRequest,
    LicenseActivateRequest,
    LicenseOut,
    LicenseStatusResponse,
    LoginRequest,
    MetricsPayload,
    PredictionResponse,
    TokenResponse,
    TopologyLinkOut,
    TopologyMapResponse,
    UserCreate,
    UserOut,
)

logger = logging.getLogger(__name__)

# ─── Auth helpers ─────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: Dict[str, Any], expire_delta: datetime.timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.datetime.utcnow() + expire_delta
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TOKEN", "message": str(exc)},
        )


# ─── WebSocket connection manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, message: str) -> None:
        dead: List[WebSocket] = []
        for connection in self.active:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active.remove(d)


ws_manager = ConnectionManager()


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    init_db()
    # Pre-generate the server quantum keypair on startup
    get_quantum_keypair()
    logger.info("OmniNet Quantum-Core started.")
    yield
    logger.info("OmniNet Quantum-Core shutting down.")


app = FastAPI(
    title="OmniNet Quantum-Core",
    description="Universal Network Orchestrator — post-quantum AAA + AI prediction.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ─── Helper: current user from Bearer token ───────────────────────────────────

async def get_current_user(
    token: str = Depends(
        lambda: None  # replaced below
    ),
    db: Session = Depends(get_db),
) -> User:
    # Implemented via explicit header parsing in each route
    raise NotImplementedError


from fastapi.security import OAuth2PasswordBearer  # noqa: E402

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def current_user_dep(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = _decode_token(token)
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail={"error_code": "INVALID_TOKEN", "message": "Missing sub."})
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail={"error_code": "USER_NOT_FOUND", "message": "User not found."})
    return user


# ─── Auth routes ─────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=APIResponse, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> APIResponse:
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=409,
            detail={"error_code": "USERNAME_TAKEN", "message": "Username already exists."},
        )
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=_hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return APIResponse(data=UserOut.model_validate(user).model_dump())


@app.post("/api/auth/login", response_model=APIResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> APIResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not _verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Invalid username or password."},
        )
    access_token = _create_token(
        {"sub": user.username},
        datetime.timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = _create_token(
        {"sub": user.username, "type": "refresh"},
        datetime.timedelta(days=settings.refresh_token_expire_days),
    )
    token_data = TokenResponse(access_token=access_token, refresh_token=refresh_token)
    return APIResponse(data=token_data.model_dump())


@app.post("/api/auth/refresh", response_model=APIResponse)
def refresh_token(token: str, db: Session = Depends(get_db)) -> APIResponse:
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail={"error_code": "NOT_REFRESH_TOKEN", "message": "Provide a refresh token."})
    username: str = payload.get("sub", "")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail={"error_code": "USER_NOT_FOUND", "message": "User not found."})
    access_token = _create_token(
        {"sub": user.username},
        datetime.timedelta(minutes=settings.access_token_expire_minutes),
    )
    return APIResponse(data={"access_token": access_token, "token_type": "bearer"})


# ─── Device routes ────────────────────────────────────────────────────────────

@app.get("/api/devices", response_model=APIResponse)
def list_devices(
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    devices = db.query(Device).all()
    return APIResponse(
        data=[DeviceOut.model_validate(d).model_dump() for d in devices],
        meta={"total": len(devices)},
    )


@app.post("/api/devices", response_model=APIResponse, status_code=201)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
    lm: LicenseManager = Depends(get_license_manager),
) -> APIResponse:
    current_count = db.query(Device).count()
    lm.check_device_limit(current_count)
    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return APIResponse(data=DeviceOut.model_validate(device).model_dump())


@app.get("/api/devices/{device_id}", response_model=APIResponse)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Device not found."})
    return APIResponse(data=DeviceOut.model_validate(device).model_dump())


@app.delete("/api/devices/{device_id}", response_model=APIResponse)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Device not found."})
    db.delete(device)
    db.commit()
    return APIResponse(data={"deleted": device_id})


# ─── Topology routes ──────────────────────────────────────────────────────────

@app.post("/api/topology/discover", response_model=APIResponse)
def discover_topology(
    payload: DiscoverRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
    lm: LicenseManager = Depends(get_license_manager),
) -> APIResponse:
    lm.check_feature_access("basic_topology")
    engine = NetworkDiscoveryEngine()
    credentials = {
        "username": payload.username,
        "password": payload.password,
        "device_type": payload.device_type,
        "secret": payload.secret,
    }
    result = engine.build_topology_graph([payload.seed_ip], credentials)

    created_devices: List[Device] = []
    for node in result["nodes"]:
        existing = db.query(Device).filter(Device.ip_address == node["ip_address"]).first()
        if not existing:
            current_count = db.query(Device).count()
            try:
                lm.check_device_limit(current_count)
            except HTTPException:
                break
            device = Device(
                hostname=node.get("hostname", node["ip_address"]),
                ip_address=node["ip_address"],
                device_type=node.get("device_type", "unknown"),
                vendor=node.get("vendor", "unknown"),
                os_version=node.get("os_version", "unknown"),
                status="online",
                last_seen=datetime.datetime.utcnow(),
            )
            db.add(device)
            db.flush()
            created_devices.append(device)

    db.commit()
    return APIResponse(
        data={"discovered": len(created_devices), "links": result["links"]},
        meta={"seed_ip": payload.seed_ip},
    )


@app.get("/api/topology/map", response_model=APIResponse)
def topology_map(
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    devices = db.query(Device).all()
    links = db.query(TopologyLink).all()
    data = TopologyMapResponse(
        nodes=[DeviceOut.model_validate(d) for d in devices],
        links=[TopologyLinkOut.model_validate(l) for l in links],
    )
    return APIResponse(data=data.model_dump())


# ─── AI routes ───────────────────────────────────────────────────────────────

@app.post(
    "/api/ai/train/{device_id}",
    response_model=APIResponse,
    dependencies=[Depends(require_feature("ai_prediction"))],
)
def train_model(
    device_id: int,
    historical_data: List[MetricsPayload],
    predictor: FailurePredictor = Depends(get_predictor),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    predictor.train(device_id, [m.model_dump() for m in historical_data])
    return APIResponse(data={"trained": True, "samples": len(historical_data)})


@app.get(
    "/api/ai/predict/{device_id}",
    response_model=APIResponse,
    dependencies=[Depends(require_feature("ai_prediction"))],
)
def predict_failure(
    device_id: int,
    cpu_percent: float = 50.0,
    ram_percent: float = 50.0,
    error_rate: float = 0.0,
    latency_ms: float = 10.0,
    db: Session = Depends(get_db),
    predictor: FailurePredictor = Depends(get_predictor),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    metrics = {
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "error_rate": error_rate,
        "latency_ms": latency_ms,
    }
    probability, ttf = predictor.predict(device_id, metrics)
    alert_created = False
    if probability >= 0.75:
        alert = predictor.generate_alert(device_id, (probability, ttf), db)
        alert_created = alert is not None

    result = PredictionResponse(
        device_id=device_id,
        failure_probability=probability,
        time_to_failure_hours=ttf,
        alert_created=alert_created,
        message=f"Failure probability: {probability * 100:.1f}%",
    )
    return APIResponse(data=result.model_dump())


# ─── License routes ───────────────────────────────────────────────────────────

@app.post("/api/license/activate", response_model=APIResponse)
def activate_license(
    payload: LicenseActivateRequest,
    lm: LicenseManager = Depends(get_license_manager),
    _user: User = Depends(current_user_dep),
) -> APIResponse:
    record = lm.activate_license(payload.key)
    return APIResponse(data=LicenseOut.model_validate(record).model_dump())


@app.get("/api/license/status", response_model=APIResponse)
def license_status(
    lm: LicenseManager = Depends(get_license_manager),
) -> APIResponse:
    status_data = lm.get_license_status()
    return APIResponse(data=LicenseStatusResponse(**status_data).model_dump())


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/topology")
async def ws_topology(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            devices = db.query(Device).all()
            links = db.query(TopologyLink).all()
            payload = {
                "type": "topology_update",
                "data": {
                    "nodes": [DeviceOut.model_validate(d).model_dump() for d in devices],
                    "links": [TopologyLinkOut.model_validate(l).model_dump() for l in links],
                },
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
            await websocket.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "omninet-quantum-core"}


# ─── Global error handler ─────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Any, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        body = {"status": "error", **detail}
    else:
        body = {"status": "error", "error_code": "HTTP_ERROR", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=body)

