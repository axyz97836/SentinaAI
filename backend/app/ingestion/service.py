"""Durable upload intent precedes object writes; jobs also serve as publication records."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.errors import AuthError
from app.auth.service import Principal
from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import UploadMetadata, safe_filename
from app.models import AuditLog, Dataset, Job, Organization
from app.observability import configure_logging

Publish = Callable[[str, str], None]
logger = configure_logging()


def finish(job: Job, code: str | None = None) -> None:
    job.status = "FAILED" if code else "SUCCEEDED"
    job.error_code = code
    job.error_message = (
        "An admin must activate a model before scoring."
        if code == "ACTIVE_MODEL_REQUIRED"
        else "Dataset processing could not be completed. See the error code."
        if code
        else None
    )
    job.completed_at = datetime.now(UTC)


def accept_upload(
    sessions: sessionmaker[Session],
    storage: PrivateStorage,
    principal: Principal,
    metadata: UploadMetadata,
    file: BinaryIO,
    filename: str,
    size: int,
    request_id: str,
) -> tuple[UUID, UUID]:
    dataset_id, job_id = uuid4(), uuid4()
    checksum = sha256()
    while chunk := file.read(64 * 1024):
        checksum.update(chunk)
    digest = checksum.hexdigest()
    file.seek(0)
    now = datetime.now(UTC)
    # Serialize admissions per organization so parallel requests cannot bypass the quota.
    with sessions.begin() as db:
        db.execute(
            select(Organization.id)
            .where(Organization.id == principal.organization_id)
            .with_for_update()
        ).one()
        recent = db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.organization_id == principal.organization_id,
                Job.type == "CSV_IMPORT",
                Job.created_at >= now - timedelta(minutes=5),
            )
        )
        pending = db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.organization_id == principal.organization_id,
                Job.type == "CSV_IMPORT",
                Job.status.in_(("QUEUED", "PROCESSING")),
            )
        )
        if (recent or 0) >= 10 or (pending or 0) >= 5:
            raise AuthError(429, "INGESTION_LIMIT", "Upload limit reached. Try later.", 60)
        db.add(
            Dataset(
                id=dataset_id,
                organization_id=principal.organization_id,
                uploaded_by=principal.user_id,
                purpose=metadata.purpose,
                source_kind=metadata.source_kind,
                license_reference=metadata.license_reference,
                original_filename=safe_filename(filename),
                object_key=storage.key(principal.organization_id, dataset_id),
                sha256=digest,
                size_bytes=size,
                status="UPLOADED",
            )
        )
        db.flush()
        db.add(
            Job(
                id=job_id,
                organization_id=principal.organization_id,
                requested_by=principal.user_id,
                dataset_id=dataset_id,
                type="CSV_IMPORT",
                status="QUEUED",
                params_json={"upload_ready": False},
            )
        )
    # Hold the job lock during the bounded object write; reconciliation cannot delete a live put.
    try:
        with sessions.begin() as db:
            job = db.scalars(select(Job).where(Job.id == job_id).with_for_update()).one()
            if job.status != "QUEUED" or job.params_json.get("upload_ready"):
                raise AuthError(409, "UPLOAD_INTERRUPTED", "Upload is no longer available.")
            storage.put(principal.organization_id, dataset_id, file, size)
            job.params_json = {"upload_ready": True}
            db.add(
                AuditLog(
                    organization_id=principal.organization_id,
                    actor_user_id=principal.user_id,
                    action="DATASET_UPLOADED",
                    resource_type="DATASET",
                    resource_id=dataset_id,
                    metadata_json={
                        "purpose": metadata.purpose,
                        "source_kind": metadata.source_kind,
                    },
                    request_id=request_id,
                )
            )
    except StorageUnavailable:
        # Leave durable intent for reconciliation, including an ambiguous successful PUT.
        raise AuthError(
            503, "STORAGE_UNAVAILABLE", "Upload storage is temporarily unavailable."
        ) from None
    return job_id, dataset_id


def cleanup_object(job: Job, dataset: Dataset, storage: PrivateStorage) -> None:
    try:
        storage.delete(job.organization_id, dataset.id)
    except StorageUnavailable:
        job.params_json = {
            **job.params_json,
            "cleanup_pending": True,
            "cleanup_error_code": "STORAGE_DELETE_UNAVAILABLE",
        }
        logger.warning(
            "ingestion object cleanup unavailable",
            extra={
                "action": "ingestion_cleanup",
                "error_code": "STORAGE_DELETE_UNAVAILABLE",
                "job_id": str(job.id),
            },
        )
    else:
        job.params_json = {
            **job.params_json,
            "cleanup_pending": False,
            "cleanup_error_code": None,
        }


def reconcile(sessions: sessionmaker[Session], storage: PrivateStorage, publish: Publish) -> None:
    """Bounded recovery pass, run by API lifespan even when Redis has lost messages."""
    now = datetime.now(UTC)
    with sessions() as db:
        identifiers = list(
            db.scalars(
                select(Job.id)
                .where(
                    Job.type == "CSV_IMPORT",
                    or_(
                        Job.status.in_(("QUEUED", "PROCESSING")),
                        Job.params_json["cleanup_pending"].as_boolean().is_(True),
                    ),
                )
                .order_by(Job.created_at)
                .limit(100)
            )
        )
    for identifier in identifiers:
        with sessions.begin() as db:
            job = db.scalar(
                select(Job).where(Job.id == identifier).with_for_update(skip_locked=True)
            )
            if job is None:
                continue
            dataset = db.scalar(
                select(Dataset).where(
                    Dataset.id == job.dataset_id, Dataset.organization_id == job.organization_id
                )
            )
            if dataset is None:
                if job.status in {"QUEUED", "PROCESSING"}:
                    finish(job, "DATASET_MISSING")
                continue
            if job.params_json.get("cleanup_pending") and dataset.status == "REJECTED":
                cleanup_object(job, dataset, storage)
            if job.status not in {"QUEUED", "PROCESSING"}:
                continue
            if not job.params_json.get("upload_ready"):
                if job.created_at < now - timedelta(minutes=5):
                    dataset.status = "REJECTED"
                    finish(job, "UPLOAD_INTERRUPTED")
                    cleanup_object(job, dataset, storage)
                continue
            next_publish = job.params_json.get("next_publish_at", 0)
            if isinstance(next_publish, (int, float)) and next_publish > now.timestamp():
                continue
            # The advisory lock in the worker protects against all duplicate publications.
            try:
                publish(str(job.id), str(dataset.id))
            except Exception:
                logger.warning(
                    "ingestion publication unavailable",
                    extra={
                        "action": "ingestion_publish",
                        "error_code": "BROKER_UNAVAILABLE",
                        "job_id": str(job.id),
                    },
                )
                continue
            job.params_json = {**job.params_json, "next_publish_at": now.timestamp() + 60}
