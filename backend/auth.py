# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/auth.py — JWT authentication and user management

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import redis as _redis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY_64_CHARS_MINIMUM"

SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    logger.warning(
        "SECRET_KEY is not set via environment variable. "
        "Using the insecure default. Set SECRET_KEY in production."
    )

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# ── Admin credentials from environment ───────────────────────────────────────
_DEFAULT_ADMIN_PASSWORD = "OmniNet2026!"
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_DEFAULT_EMAIL", "admin@omninet.local")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", _DEFAULT_ADMIN_PASSWORD)

_environment = os.getenv("ENVIRONMENT", "production").lower()
if DEFAULT_ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD and _environment not in ("test", "development"):
    raise RuntimeError(
        "FATAL: ADMIN_DEFAULT_PASSWORD is set to the insecure default 'OmniNet2026!'. "
        "Set ADMIN_DEFAULT_PASSWORD in your .env file before starting in production."
    )

# ── Account lockout (Redis) ───────────────────────────────────────────────────
_LOCKOUT_MAX_ATTEMPTS = 5
_LOCKOUT_TTL_SECONDS = 15 * 60  # 15 minutes

_redis_url = os.getenv("REDIS_URL", "")
_redis_client: Optional[_redis.Redis] = None
if _redis_url:
    try:
        _redis_client = _redis.Redis.from_url(_redis_url, decode_responses=True)
        _redis_client.ping()
    except Exception as exc:
        logger.warning("auth: Redis unavailable — account lockout disabled: %s", exc)
        _redis_client = None


def _lockout_key(email: str) -> str:
    return f"auth:lockout:{email}"


def _is_account_locked(email: str) -> bool:
    """Return True if the account is currently locked out."""
    if _redis_client is None:
        return False
    try:
        attempts = _redis_client.get(_lockout_key(email))
        return attempts is not None and int(attempts) >= _LOCKOUT_MAX_ATTEMPTS
    except Exception:
        return False


def _record_failed_attempt(email: str) -> int:
    """Increment and return the failed attempt counter for *email*."""
    if _redis_client is None:
        return 0
    try:
        key = _lockout_key(email)
        count = _redis_client.incr(key)
        if count == 1:
            _redis_client.expire(key, _LOCKOUT_TTL_SECONDS)
        return count
    except Exception:
        return 0


def _clear_failed_attempts(email: str) -> None:
    """Clear the failed attempt counter on successful login."""
    if _redis_client is None:
        return
    try:
        _redis_client.delete(_lockout_key(email))
    except Exception:
        pass


# ── Password utilities ────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[models.User]:
    """Authenticate a user with lockout protection.

    Returns None on failure (unknown email *or* wrong password) so callers
    cannot distinguish the two cases — preventing user-enumeration attacks.
    Also enforces an account lockout after :data:`_LOCKOUT_MAX_ATTEMPTS`
    consecutive failures (TTL :data:`_LOCKOUT_TTL_SECONDS`).
    """
    if _is_account_locked(email):
        logger.warning("auth: account locked out for email=%s", email)
        return None

    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        _record_failed_attempt(email)
        return None

    _clear_failed_attempts(email)
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=token_data.email)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def ensure_default_admin(db: Session) -> None:
    """Create the default admin user if the users table is empty."""
    if db.query(models.User).count() == 0:
        admin = models.User(
            email=DEFAULT_ADMIN_EMAIL,
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            is_active=True,
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
