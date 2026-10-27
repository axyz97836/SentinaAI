"""Durable training with one candidate identity per job and bounded infrastructure retries."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.ingestion.service import Publish, finish
from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import InvalidCSV
from app.jobs import job_session
from app.ml import artifacts
from app.ml.data import load_rows
from app.ml.runtime import require_authoritative_runtime
from app.ml.service import provenance
from app.ml.training import WEIGHTS, train
from app.models import AuditLog, Dataset, Job, ModelVersion
from app.observability import configure_logging

logger = configure_logging()


def fail(job: Job, code: str) -> None:
    finish(job, code)
    job.error_message = "Model training could not be completed. See the error code."
    job.params_json = {**job.params_json, "artifact_cleanup_pending": True}


def process_training(
    engine: Engine, storage: PrivateStorage, job_id: UUID, dataset_id: UUID
) -> bool:
    with job_session(engine, job_id) as db:
        if db is None:
            return False
        with db.begin():
            job = db.scalar(
                select(Job)
                .where(Job.id == job_id, Job.dataset_id == dataset_id, Job.type == "MODEL_TRAIN")
                .with_for_update()
            )
            if job is None or job.status in {"SUCCEEDED", "FAILED"}:
                return False
            dataset = db.scalar(
                select(Dataset).where(
                    Dataset.id == dataset_id, Dataset.organization_id == job.organization_id
                )
            )
            if dataset is None:
                fail(job, "DATASET_MISSING")
                return False
            if job.attempt_count >= 3:
                fail(job, "RETRY_EXHAUSTED")
                return False
            if job.params_json.get("retry_at", 0) > datetime.now(UTC).timestamp():
                return False
            candidate = UUID(job.params_json["candidate_id"])
            job.attempt_count += 1
            job.status = "PROCESSING"
            job.started_at = job.started_at or datetime.now(UTC)
            job.error_code = job.error_message = None
        try:
            require_authoritative_runtime()
            rows = load_rows(dataset, job.organization_id, storage)
            bundle = train(rows, provenance(job, dataset, candidate))
            content = artifacts.pack(bundle)
            digest = sha256(content).hexdigest()
            with db.begin():
                # Recheck durable ownership before an object write after long CPU work.
                db.refresh(job, with_for_update=True)
                if job.status in {"SUCCEEDED", "FAILED"}:
                    return False
                artifacts.put(storage, job.organization_id, candidate, content)
                # Confirm the actual stored bytes before publishing any candidate metadata.
                artifacts.unpack_verified(
                    artifacts.read(storage, job.organization_id, candidate),
                    digest,
                    bundle.provenance,
                    bundle.feature_schema,
                )
                model = ModelVersion(
                    id=candidate,
                    organization_id=job.organization_id,
                    training_dataset_id=dataset.id,
                    version_label=f"ml-{candidate.hex}",
                    algorithm="LogisticRegression + IsolationForest",
                    artifact_key=artifacts.key(job.organization_id, candidate),
                    artifact_sha256=digest,
                    feature_schema_json=bundle.feature_schema,
                    metrics_json=bundle.metrics,
                    weight_config_json=WEIGHTS,
                    is_active=False,
                    trained_at=datetime.now(UTC),
                )
                db.add(model)
                db.flush()
                job.model_version_id = candidate
                job.total_rows = job.processed_rows = len(rows)
                finish(job)
                db.add(
                    AuditLog(
                        organization_id=job.organization_id,
                        actor_user_id=job.requested_by,
                        action="MODEL_TRAINED",
                        resource_type="MODEL",
                        resource_id=candidate,
                        metadata_json={"job_id": str(job.id), "dataset_id": str(dataset.id)},
                    )
                )
        except InvalidCSV as exc:
            with db.begin():
                db.refresh(job, with_for_update=True)
                if job.status not in {"SUCCEEDED", "FAILED"}:
                    fail(job, exc.code)
        except StorageUnavailable:
            with db.begin():
                db.refresh(job, with_for_update=True)
                if job.status in {"SUCCEEDED", "FAILED"}:
                    return False
                if job.attempt_count >= 3:
                    fail(job, "STORAGE_UNAVAILABLE")
                else:
                    retry_at = datetime.now(UTC).timestamp() + 5 * 2**job.attempt_count
                    job.status = "QUEUED"
                    job.error_code = "STORAGE_UNAVAILABLE"
                    job.error_message = "Storage is unavailable. A retry is scheduled."
                    job.params_json = {
                        **job.params_json,
                        "retry_at": retry_at,
                        "next_publish_at": retry_at,
                    }
            return job.status == "QUEUED"
        return False


def reconcile_training(
    sessions: sessionmaker[Session], storage: PrivateStorage, publish: Publish
) -> None:
    now = datetime.now(UTC).timestamp()
    with sessions() as db:
        identifiers = list(
            db.scalars(
                select(Job.id)
                .where(
                    Job.type == "MODEL_TRAIN",
                    or_(
                        Job.status.in_(("QUEUED", "PROCESSING")),
                        Job.params_json["artifact_cleanup_pending"].as_boolean().is_(True),
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
            if job.status == "FAILED" and job.params_json.get("artifact_cleanup_pending"):
                try:
                    artifacts.delete(
                        storage, job.organization_id, UUID(job.params_json["candidate_id"])
                    )
                except StorageUnavailable:
                    continue
                job.params_json = {**job.params_json, "artifact_cleanup_pending": False}
            if (
                job.status not in {"QUEUED", "PROCESSING"}
                or job.params_json.get("next_publish_at", 0) > now
            ):
                continue
            try:
                publish(str(job.id), str(job.dataset_id))
            except Exception:
                logger.warning(
                    "training publication unavailable",
                    extra={
                        "action": "model_publish",
                        "job_id": str(job.id),
                        "error_code": "BROKER_UNAVAILABLE",
                    },
                )
                continue
            job.params_json = {**job.params_json, "next_publish_at": now + 60}
