"""Database engine/session setup.

Works transparently against SQLite (zero-config local dev, tests) or
PostgreSQL (staging/production) — the connection target is entirely
controlled by `DATABASE_URL`.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Used for local/dev bootstrapping and tests.

    Production deployments should use Alembic migrations instead.
    """
    from app.database import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
