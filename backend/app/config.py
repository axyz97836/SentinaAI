from functools import lru_cache
from typing import Literal
from urllib.parse import quote, urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["local", "test", "production"] = "local"
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
    auth_secret: SecretStr | None = Field(default=None, min_length=64, repr=False)
    auth_cookie_secure: bool = True
    auth_allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    )
    auth_session_seconds: int = Field(default=28800, ge=300, le=86400)
    auth_idle_seconds: int = Field(default=1800, ge=60, le=86400)
    auth_login_window_seconds: int = Field(default=300, ge=10, le=3600)
    auth_login_ip_limit: int = Field(default=20, ge=1, le=1000)
    auth_login_account_limit: int = Field(default=5, ge=1, le=100)

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset(value.strip() for value in self.auth_allowed_origins.split(","))

    @property
    def session_cookie(self) -> str:
        return "__Host-sentinel_session" if self.auth_cookie_secure else "sentinel_session"

    @property
    def preauth_cookie(self) -> str:
        return "__Host-sentinel_preauth" if self.auth_cookie_secure else "sentinel_preauth"

    @model_validator(mode="after")
    def validate_auth_policy(self) -> "Settings":
        if self.auth_idle_seconds > self.auth_session_seconds:
            raise ValueError("Idle timeout must not exceed absolute session lifetime")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Configure exact HTTP(S) origins without paths or credentials")
            loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if self.app_env == "production" and (
                parsed.scheme != "https" or not self.auth_cookie_secure or not self.auth_secret
            ):
                raise ValueError(
                    "Production requires HTTPS origins, Secure cookies and auth secret"
                )
            if not self.auth_cookie_secure and not (
                loopback or (self.app_env == "test" and parsed.hostname == "testserver")
            ):
                raise ValueError("Insecure cookies are restricted to local loopback/test origins")
        return self

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
