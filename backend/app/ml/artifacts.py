"""Only verified worker-produced bundles cross this deserialization boundary."""

import io
import json
import pickle
from hashlib import sha256
from typing import Any
from uuid import UUID

import numpy as np
from botocore.exceptions import BotoCoreError, ClientError

from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import InvalidCSV
from app.ml.training import FEATURE_SCHEMA, BaselineBundle, dependencies

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAGIC = b"SENTINELAI-BASELINE-1\n"


def key(organization_id: UUID, model_id: UUID) -> str:
    return f"organizations/{organization_id}/models/{model_id}.bundle"


def pack(bundle: BaselineBundle) -> bytes:
    header = json.dumps(
        {
            "dependencies": dependencies(),
            "provenance": bundle.provenance,
            "feature_schema": bundle.feature_schema,
        },
        sort_keys=True,
    ).encode()
    content = MAGIC + header + b"\n" + pickle.dumps(bundle, protocol=5)
    if len(content) > MAX_ARTIFACT_BYTES:
        raise InvalidCSV("ARTIFACT_TOO_LARGE")
    return content


def unpack_verified(
    content: bytes, digest: str, provenance: dict[str, str], schema: dict[str, Any]
) -> BaselineBundle:
    # Call only after the database confirms a successful worker job and matching model provenance.
    if len(content) > MAX_ARTIFACT_BYTES or sha256(content).hexdigest() != digest:
        raise InvalidCSV("ARTIFACT_INTEGRITY_FAILED")
    if not content.startswith(MAGIC):
        raise InvalidCSV("ARTIFACT_FORMAT_UNSUPPORTED")
    try:
        header, payload = content[len(MAGIC) :].split(b"\n", 1)
        if len(header) > 64 * 1024:
            raise ValueError()
        metadata = json.loads(header)
        if metadata != {
            "dependencies": dependencies(),
            "provenance": provenance,
            "feature_schema": schema,
        } or any(schema.get(k) != v for k, v in FEATURE_SCHEMA.items()):
            raise ValueError()
        # Private key, DB digest and successful MODEL_TRAIN provenance must be checked first.
        # Pickle is executable: compromise of BOTH trusted DB metadata and storage is out of scope.
        stream = io.BytesIO(payload)
        bundle = pickle.load(stream)  # noqa: S301 - trusted producer verified before deserialization.
        if stream.read(1) or type(bundle) is not BaselineBundle:
            raise ValueError()
        if bundle.provenance != provenance or bundle.feature_schema != schema:
            raise ValueError()
        if (
            bundle.reference.ndim != 1
            or not 20 <= len(bundle.reference) <= 10_000
            or not np.isfinite(bundle.reference).all()
            or not np.all(bundle.reference[:-1] <= bundle.reference[1:])
            or bundle.supervised.named_steps["preprocessing"].get_feature_names_out().tolist()
            != schema["transformed_names"]
        ):
            raise ValueError()
        return bundle
    except Exception:
        raise InvalidCSV("ARTIFACT_INCOMPATIBLE") from None


def put(storage: PrivateStorage, org: UUID, model: UUID, content: bytes) -> None:
    if not 0 < len(content) <= MAX_ARTIFACT_BYTES:
        raise InvalidCSV("ARTIFACT_TOO_LARGE")
    try:
        storage.client.put_object(
            Bucket=storage.bucket,
            Key=key(org, model),
            Body=content,
            ContentLength=len(content),
            ContentType="application/octet-stream",
        )
    except (ClientError, BotoCoreError):
        raise StorageUnavailable() from None


def read(storage: PrivateStorage, org: UUID, model: UUID) -> bytes:
    try:
        response = storage.client.get_object(Bucket=storage.bucket, Key=key(org, model))
        with response["Body"] as body:
            content = body.read(MAX_ARTIFACT_BYTES + 1)
        if len(content) > MAX_ARTIFACT_BYTES or len(content) != response["ContentLength"]:
            raise InvalidCSV("ARTIFACT_INTEGRITY_FAILED")
        return content
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"NoSuchKey", "404"}:
            raise InvalidCSV("ARTIFACT_MISSING") from None
        raise StorageUnavailable() from None
    except BotoCoreError:
        raise StorageUnavailable() from None


def delete(storage: PrivateStorage, org: UUID, model: UUID) -> None:
    try:
        storage.client.delete_object(Bucket=storage.bucket, Key=key(org, model))
    except (ClientError, BotoCoreError):
        raise StorageUnavailable() from None
