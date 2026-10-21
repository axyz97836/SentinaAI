from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from tempfile import TemporaryFile
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.ingestion.validation import MAX_BYTES, InvalidCSV


class StorageUnavailable(Exception):
    """Safe transient error; never propagate provider messages to Celery logs."""


class PrivateStorage:
    def __init__(self, settings: Settings):
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            config=Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    @staticmethod
    def key(organization_id: UUID, dataset_id: UUID) -> str:
        return f"organizations/{organization_id}/datasets/{dataset_id}.csv"

    def put(self, organization_id: UUID, dataset_id: UUID, file: BinaryIO, size: int) -> None:
        file.seek(0)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self.key(organization_id, dataset_id),
                Body=file,
                ContentLength=size,
                ContentType="text/csv",
            )
        except (BotoCoreError, ClientError):
            raise StorageUnavailable() from None

    def delete(self, organization_id: UUID, dataset_id: UUID) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self.key(organization_id, dataset_id))
        except (BotoCoreError, ClientError):
            raise StorageUnavailable() from None

    @contextmanager
    def read(
        self, organization_id: UUID, dataset_id: UUID, size: int, digest: str
    ) -> Iterator[BinaryIO]:
        try:
            response = self.client.get_object(
                Bucket=self.bucket, Key=self.key(organization_id, dataset_id)
            )
            with response["Body"] as body, TemporaryFile() as file:
                checksum = sha256()
                total = 0
                while chunk := body.read(64 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES or total > size:
                        raise InvalidCSV("OBJECT_INTEGRITY_FAILED")
                    checksum.update(chunk)
                    file.write(chunk)
                if total != size or checksum.hexdigest() != digest:
                    raise InvalidCSV("OBJECT_INTEGRITY_FAILED")
                file.seek(0)
                yield file
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                raise InvalidCSV("OBJECT_MISSING") from None
            raise StorageUnavailable() from None
        except BotoCoreError:
            raise StorageUnavailable() from None

    def close(self) -> None:
        self.client.close()
