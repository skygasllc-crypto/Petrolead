# ruff: noqa: E402 — env vars below must be set before any `app.*` import.
from __future__ import annotations

import os

# Force an isolated, ephemeral database and mock search provider for the
# whole test session — must happen before any `app.*` module is imported,
# since settings are read (and cached) at import time.
#
# This file-based DB is only ever touched by the app's lifespan
# (init_db() -> create_all()) — actual test data goes through the
# in-memory `db_session` fixture below via a dependency override. It
# still needs a real, working SQLite file though, and this project
# directory lives on a WSL-mounted Windows drive (/mnt/c), where SQLite
# intermittently throws "disk I/O error" (see the wsl_sqlite_io_errors
# memory) — so it's placed on the native filesystem instead of relative
# to the repo.
_TEST_DB_PATH = "/tmp/petrolead-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["SEARCH_PROVIDER"] = "mock"
# Otherwise a developer's local .env ADMIN_EMAILS would leak into test
# behavior (e.g. an admin test's own dependency-override "current admin"
# accidentally matching that address) — tests set admin status explicitly.
os.environ["ADMIN_EMAILS"] = ""

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
def unauthenticated_client(db_session):
    """A TestClient with no Authorization header — for auth tests themselves."""
    from fastapi.testclient import TestClient

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client(unauthenticated_client):
    """The default client: a real registered user, pre-authenticated.

    Every endpoint except /api/auth/* and /api/health requires a logged-in
    user, so most tests (which are about discovery/companies/etc., not
    auth itself) should default to being authenticated rather than each
    having to register+log in a user by hand.
    """
    response = unauthenticated_client.post(
        "/api/auth/register",
        json={"email": "test-user@example.com", "password": "correct-horse-battery"},
    )
    token = response.json()["access_token"]
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"
    return unauthenticated_client


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_db_file():
    yield
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)
