"""Apply Alembic migrations — on app startup (`RUN_MIGRATIONS_ON_STARTUP`) or from tests.

The migration scripts themselves live in `alembic/versions/`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

logger = logging.getLogger("petrolead.database.migrations")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The first migration: the schema as it stood when migrations were introduced.
INITIAL_REVISION = "0001"

# Tables a database created before migrations existed may still be missing,
# depending on which version of the app first created it. They're created
# from today's models, so any later migration that changes one of these
# tables must allow for the change already being there (see 0003).
_TABLES_OLDER_DATABASES_MAY_LACK = ("users", "subscriptions", "credit_transactions")


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def run_migrations(database_url: str | None = None) -> None:
    """Bring the database schema up to date.

    A database whose tables were made by the app's old `create_all()`
    startup — before migrations existed — has no `alembic_version` table.
    It's adopted at the initial revision (after creating any tables it's
    missing) rather than having its existing tables created a second time.
    """
    if database_url is None:
        from app.config import get_settings

        database_url = get_settings().database_url
    config = alembic_config(database_url)

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "companies" in tables:
            from app.database import models  # noqa: F401 — registers every table
            from app.database.connection import Base

            missing = [
                Base.metadata.tables[name]
                for name in _TABLES_OLDER_DATABASES_MAY_LACK
                if name not in tables
            ]
            if missing:
                Base.metadata.create_all(engine, tables=missing)
            logger.info("Adopting an existing database into migrations at %s", INITIAL_REVISION)
            command.stamp(config, INITIAL_REVISION)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
