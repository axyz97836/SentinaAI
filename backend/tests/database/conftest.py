"""All destructive database tests are restricted to the private disposable service."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.database import MigrationSettings, database_engine


@pytest.fixture(scope="session")
def migration_config() -> Config:
    if os.environ.get("DATABASE_TESTS") != "1":
        pytest.skip("Run make database-check for the isolated PostgreSQL tests")
    settings = MigrationSettings()
    if (settings.app_env, settings.db_host, settings.postgres_db) != (
        "test",
        "database-test",
        "sentinelai_schema_test",
    ):
        pytest.fail("Refusing to run destructive tests outside the disposable database")
    return Config(str(Path(__file__).parents[2] / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_engine(migration_config: Config) -> Iterator[Engine]:
    engine = database_engine(MigrationSettings().database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "sentinelai_schema_test"
        assert connection.scalar(text("SELECT current_user")) == "sentinel_migrator"
    # Round-trip before any fixtures: never drop a database with test/user records in it.
    command.upgrade(migration_config, "head")
    command.downgrade(migration_config, "base")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
            == 0
        )
    command.upgrade(migration_config, "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Connection]:
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
