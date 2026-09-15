"""Tests for the Alembic migrations and the startup migration runner.

Each test works on its own throwaway SQLite file, never the app's database.
"""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.database import models  # noqa: F401 — registers every table
from app.database.connection import Base
from app.database.migrations import INITIAL_REVISION, alembic_config, run_migrations

OWNED_TABLES = ("companies", "search_queries", "saved_searches")
NOW = "2026-01-01 00:00:00"

# Differences between the migrated database and the models that mean a
# migration is missing (type/nullability details vary by SQLite reflection).
STRUCTURAL_CHANGES = {
    "add_table",
    "remove_table",
    "add_column",
    "remove_column",
    "add_index",
    "remove_index",
}


@pytest.fixture()
def database_url(tmp_path):
    return f"sqlite:///{tmp_path / 'migrations.db'}"


@pytest.fixture()
def engine(database_url):
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


def _head(database_url):
    return ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()


def _add_user(conn, user_id, *, is_admin=False, created_at=NOW):
    conn.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, is_active, is_admin, created_at) "
            "VALUES (:id, :email, 'x', 1, :is_admin, :created_at)"
        ),
        {
            "id": user_id,
            "email": f"{user_id}@example.com",
            "is_admin": is_admin,
            "created_at": created_at,
        },
    )


def _add_pre_ownership_data(conn):
    """One company, search and saved search, as the 0001 schema stores them."""
    conn.execute(
        text(
            "INSERT INTO companies (id, company_name, normalized_name, activities, products, "
            "keywords, relevance_score, discovered_at, updated_at) "
            "VALUES ('c1', 'Falcon Oil', 'falcon oil', '[]', '[]', '[]', 50, :now, :now)"
        ),
        {"now": NOW},
    )
    conn.execute(
        text(
            "INSERT INTO saved_searches (id, name, products, keywords, result_limit, frequency, "
            "is_active, created_at) VALUES ('s1', 'UAE diesel', '[]', '[]', 10, 'daily', 1, :now)"
        ),
        {"now": NOW},
    )
    conn.execute(
        text(
            "INSERT INTO search_queries (id, products, keywords, result_limit, status, "
            "result_count, new_company_count, duplicate_count, created_at) "
            "VALUES ('q1', '[]', '[]', 10, 'COMPLETED', 0, 0, 0, :now)"
        ),
        {"now": NOW},
    )


def _owners(engine):
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f"SELECT owner_id FROM {table}")).scalar_one()
            for table in OWNED_TABLES
        }


class TestFreshDatabase:
    def test_upgrade_builds_the_schema_the_models_describe(self, database_url, engine):
        run_migrations(database_url)
        with engine.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        structural = [d for d in diffs if isinstance(d, tuple) and d[0] in STRUCTURAL_CHANGES]
        assert structural == [], structural

    def test_owner_is_required_and_indexed_on_owned_tables(self, database_url, engine):
        run_migrations(database_url)
        inspector = inspect(engine)
        for table in OWNED_TABLES:
            owner = next(c for c in inspector.get_columns(table) if c["name"] == "owner_id")
            assert owner["nullable"] is False
            assert f"ix_{table}_owner_id" in {i["name"] for i in inspector.get_indexes(table)}
            assert any(fk["referred_table"] == "users" for fk in inspector.get_foreign_keys(table))

    def test_downgrade_removes_ownership(self, database_url, engine):
        run_migrations(database_url)
        command.downgrade(alembic_config(database_url), INITIAL_REVISION)
        for table in OWNED_TABLES:
            assert "owner_id" not in {c["name"] for c in inspect(engine).get_columns(table)}


class TestExistingData:
    def test_existing_records_go_to_the_earliest_admin(self, database_url, engine):
        config = alembic_config(database_url)
        command.upgrade(config, INITIAL_REVISION)
        with engine.begin() as conn:
            _add_user(conn, "early-member", created_at="2025-01-01 00:00:00")
            _add_user(conn, "admin", is_admin=True, created_at="2025-06-01 00:00:00")
            _add_user(conn, "later-admin", is_admin=True, created_at="2025-09-01 00:00:00")
            _add_pre_ownership_data(conn)

        command.upgrade(config, "head")

        assert _owners(engine) == {table: "admin" for table in OWNED_TABLES}

    def test_without_an_admin_the_earliest_account_gets_them(self, database_url, engine):
        config = alembic_config(database_url)
        command.upgrade(config, INITIAL_REVISION)
        with engine.begin() as conn:
            _add_user(conn, "second", created_at="2025-06-01 00:00:00")
            _add_user(conn, "first", created_at="2025-01-01 00:00:00")
            _add_pre_ownership_data(conn)

        command.upgrade(config, "head")

        assert _owners(engine) == {table: "first" for table in OWNED_TABLES}

    def test_data_without_any_account_fails_with_a_clear_message(self, database_url, engine):
        config = alembic_config(database_url)
        command.upgrade(config, INITIAL_REVISION)
        with engine.begin() as conn:
            _add_pre_ownership_data(conn)

        with pytest.raises(RuntimeError, match="no user accounts"):
            command.upgrade(config, "head")

    def test_an_empty_database_needs_no_accounts(self, database_url, engine):
        run_migrations(database_url)
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == _head(database_url)


class TestDatabaseFromBeforeMigrations:
    """Databases whose tables were made by the app's old create_all() startup."""

    def _legacy_database(self, database_url, engine, *, drop=()):
        command.upgrade(alembic_config(database_url), INITIAL_REVISION)
        with engine.begin() as conn:
            _add_user(conn, "admin", is_admin=True)
            _add_pre_ownership_data(conn)
            for table in ("alembic_version", *drop):
                conn.execute(text(f"DROP TABLE {table}"))

    def test_is_adopted_and_upgraded_without_losing_data(self, database_url, engine):
        self._legacy_database(database_url, engine)

        run_migrations(database_url)

        assert _owners(engine) == {table: "admin" for table in OWNED_TABLES}
        with engine.connect() as conn:
            name = conn.execute(text("SELECT company_name FROM companies")).scalar_one()
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert name == "Falcon Oil"
        assert version == _head(database_url)

    def test_missing_billing_tables_are_created(self, database_url, engine):
        self._legacy_database(database_url, engine, drop=("subscriptions", "credit_transactions"))

        run_migrations(database_url)

        tables = set(inspect(engine).get_table_names())
        assert {"subscriptions", "credit_transactions"} <= tables

    def test_running_again_is_a_no_op(self, database_url, engine):
        self._legacy_database(database_url, engine)
        run_migrations(database_url)
        run_migrations(database_url)
        assert _owners(engine) == {table: "admin" for table in OWNED_TABLES}
