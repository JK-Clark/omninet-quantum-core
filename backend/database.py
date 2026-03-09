# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/database.py — SQLAlchemy engine + session factory

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

_DEFAULT_DB_PASSWORD = "changeme_in_production"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.getenv("POSTGRES_USER", "omninet"),
        password=os.getenv("POSTGRES_PASSWORD", _DEFAULT_DB_PASSWORD),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        db=os.getenv("POSTGRES_DB", "omninet"),
    ),
)

if os.getenv("POSTGRES_PASSWORD", _DEFAULT_DB_PASSWORD) == _DEFAULT_DB_PASSWORD and not os.getenv("DATABASE_URL"):
    logger.warning(
        "POSTGRES_PASSWORD is not set. Using the default placeholder password. "
        "Set the POSTGRES_PASSWORD environment variable in production."
    )

# SQLite fallback for local development / CI without Postgres
if DATABASE_URL.startswith("postgresql") and os.getenv("USE_SQLITE_FALLBACK", "false").lower() == "true":
    DATABASE_URL = "sqlite:///./omninet.db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables (called at startup)."""
    Base.metadata.create_all(bind=engine)
