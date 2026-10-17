"""Real dependency checks against this project's isolated Compose services."""

from uuid import uuid4

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from redis import Redis
from redis.exceptions import AuthenticationError
from sqlalchemy import text

from app.config import get_settings
from app.health import DependencyProbe
from app.worker import celery_app


def main() -> None:
    settings = get_settings()
    probe = DependencyProbe(settings)
    try:
        assert probe.ready(), "Dependencies are not ready"
        with probe.engine.connect() as connection:
            role = connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            ).one()
            assert tuple(role) == (False, False, False), "Application database role is privileged"
            assert not connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            )
        print("PASS: PostgreSQL authenticated query and restricted application role")

        unauthenticated: Redis = Redis(host=settings.redis_host, socket_timeout=2)
        try:
            unauthenticated.ping()
        except AuthenticationError:
            print("PASS: Redis denies unauthenticated commands")
        else:
            raise AssertionError("Redis accepted unauthenticated access")
        finally:
            unauthenticated.close()

        key = f"foundation-check/{uuid4().hex}.txt"
        body = b"SentinelAI synthetic foundation test"
        unsigned = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            config=Config(signature_version=UNSIGNED, retries={"total_max_attempts": 1}),
        )
        try:
            probe.storage.put_object(Bucket=settings.s3_bucket, Key=key, Body=body)
            result = probe.storage.get_object(Bucket=settings.s3_bucket, Key=key)
            with result["Body"] as stream:
                assert stream.read() == body
            for operation, arguments in [
                (unsigned.list_objects_v2, {"Bucket": settings.s3_bucket}),
                (unsigned.get_object, {"Bucket": settings.s3_bucket, "Key": key}),
            ]:
                try:
                    operation(**arguments)
                except ClientError as error:
                    assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 403
                else:
                    raise AssertionError("Storage allowed anonymous access")
            print("PASS: S3 authenticated write/read; anonymous listing/download denied")
            try:
                probe.storage.create_bucket(Bucket=f"forbidden-{uuid4().hex}")
            except ClientError as error:
                assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 403
            else:
                raise AssertionError("Application storage identity can create arbitrary buckets")
            print("PASS: S3 identity restricted to the configured bucket")
        finally:
            probe.storage.delete_object(Bucket=settings.s3_bucket, Key=key)
            unsigned.close()

        replies = celery_app.control.ping(destination=["sentinel@worker"], timeout=5)
        assert replies == [{"sentinel@worker": {"ok": "pong"}}], "Worker did not reply"
        print("PASS: Celery worker responds through the authenticated Redis broker")
    finally:
        probe.close()


if __name__ == "__main__":
    main()
