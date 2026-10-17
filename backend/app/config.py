from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    # This scaffold intentionally refuses a production environment.
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["local", "test"] = "local"
    db_host: str = "postgres"
    db_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "sentinelai"
    app_db_user: str = "sentinel_app"
    app_db_password: SecretStr = Field(min_length=32, repr=False)
    redis_host: str = "redis"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: SecretStr = Field(min_length=32, repr=False)
    s3_endpoint: str = "http://object-storage:8333"
    s3_region: str = "us-east-1"
    s3_bucket: str = "sentinel-local"
    s3_access_key: SecretStr = Field(min_length=16, repr=False)
    s3_secret_key: SecretStr = Field(min_length=32, repr=False)

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.app_db_user,
            password=self.app_db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

    @property
    def broker_url(self) -> str:
        password = quote(self.redis_password.get_secret_value(), safe="")
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
