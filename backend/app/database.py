"""Database metadata and explicitly separated local migration configuration."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        }
    )


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["local", "test"]  # Deliberately no production/default fallback.
    db_host: str = "postgres"
    db_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "sentinelai"
    migration_db_user: Literal["sentinel_migrator"] = "sentinel_migrator"
    migration_db_password: SecretStr = Field(min_length=32, repr=False)
    app_db_user: str = "sentinel_app"

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.migration_db_user,
            password=self.migration_db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )


def database_engine(url: URL) -> Engine:
    return create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC -c lock_timeout=5000"},
    )
