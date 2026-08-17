from __future__ import annotations

import os

# Force an isolated, ephemeral database and mock search provider for the
# whole test session — must happen before any `app.*` module is imported,
# since settings are read (and cached) at import time.
os.environ["DATABASE_URL"] = "sqlite:///./test_petrolead.db"
os.environ["SEARCH_PROVIDER"] = "mock"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    # StaticPool keeps a single shared connection alive for the whole engine
    # so the app (which TestClient runs on a separate portal thread) sees
    # the same in-memory database the fixture just created tables in.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_db_file():
    yield
    for path in ("test_petrolead.db",):
        if os.path.exists(path):
            os.remove(path)
