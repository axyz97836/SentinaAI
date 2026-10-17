from collections.abc import Callable
from typing import Protocol

import boto3
from botocore.config import Config
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from sqlalchemy import create_engine, text

from app.config import Settings
from app.observability import configure_logging

logger = configure_logging()


class ReadinessProbe(Protocol):
    def ready(self) -> bool: ...


class DependencyProbe:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            pool_timeout=2,
            hide_parameters=True,
            connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
        )
        self.redis: Redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password.get_secret_value(),
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            retry=Retry(NoBackoff(), 0),
        )
        self.storage = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )
        self.bucket = settings.s3_bucket

    def database(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def cache(self) -> None:
        if not self.redis.ping():
            raise ConnectionError("Redis unavailable")

    def objects(self) -> None:
        self.storage.head_bucket(Bucket=self.bucket)

    def ready(self) -> bool:
        checks: list[tuple[str, Callable[[], None]]] = [
            ("database", self.database),
            ("broker", self.cache),
            ("storage", self.objects),
        ]
        for name, check in checks:
            try:
                check()
            except Exception:
                logger.warning(
                    "dependency unavailable",
                    extra={"action": "readiness", "dependency": name, "error_code": "UNAVAILABLE"},
                )
                return False
        return True

    def close(self) -> None:
        self.engine.dispose()
        self.redis.close()
        self.storage.close()
