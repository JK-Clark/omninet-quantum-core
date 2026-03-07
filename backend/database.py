# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://omninet:omninet@db:5432/omninet"
    secret_key: str = "CHANGEME-use-a-strong-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Session:  # type: ignore[override]
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from models import Base as ModelsBase  # noqa: F401 – registers all models
    ModelsBase.metadata.create_all(bind=engine)
