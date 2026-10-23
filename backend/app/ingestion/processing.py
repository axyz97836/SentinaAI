"""Idempotent validation with a PostgreSQL connection lock held across progress commits."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ingestion.service import finish
from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import MAX_ERRORS, InvalidCSV, validate_csv
from app.jobs import job_session
from app.models import Dataset, Job, JobError, ModelVersion


def progress(db: Session, job: Job, rows: list[tuple[int, str | None]]) -> None:
    with db.begin():
        stored = (
            db.scalar(select(func.count()).select_from(JobError).where(JobError.job_id == job.id))
            or 0
        )
        for number, code in rows:
            if code:
                job.failed_rows += 1
                if stored < MAX_ERRORS:
                    db.add(
                        JobError(
                            job_id=job.id,
                            row_number=number,
                            code=code,
                            summary="Row does not satisfy the canonical CSV contract.",
                        )
                    )
                    stored += 1
            else:
                job.processed_rows += 1


def validate_job(db: Session, job: Job, dataset: Dataset, storage: PrivateStorage) -> None:
    completed = job.processed_rows + job.failed_rows
    with storage.read(job.organization_id, dataset.id, dataset.size_bytes, dataset.sha256) as file:
        batch: list[tuple[int, str | None]] = []
        try:
            for number, code in validate_csv(file):
                if number <= completed:
                    continue
                batch.append((number, code))
                if len(batch) == 250:
                    progress(db, job, batch)
                    batch = []
        finally:
            # Preserve genuinely examined rows even when a later record is malformed.
            if batch:
                progress(db, job, batch)
    with db.begin():
        job.total_rows = job.processed_rows + job.failed_rows
        dataset.row_count = job.total_rows
        if job.failed_rows:
            dataset.status = "REJECTED"
            job.params_json = {**job.params_json, "cleanup_pending": True}
            finish(job, "ROW_VALIDATION_FAILED")
        else:
            dataset.status = "VALIDATED"
            if dataset.purpose == "TRAINING":
                finish(job)
            else:
                active = db.scalar(
                    select(ModelVersion.id).where(
                        ModelVersion.organization_id == job.organization_id,
                        ModelVersion.is_active.is_(True),
                    )
                )
                finish(job, "ACTIVE_MODEL_REQUIRED" if active is None else "SCORING_NOT_AVAILABLE")


def process_job(engine: Engine, storage: PrivateStorage, job_id: UUID, dataset_id: UUID) -> bool:
    """Return True for a transient failure; only durable attempt_count controls exhaustion."""
    with job_session(engine, job_id) as db:
        if db is None:
            return False
        with db.begin():
            job = db.scalar(
                select(Job)
                .where(Job.id == job_id, Job.dataset_id == dataset_id, Job.type == "CSV_IMPORT")
                .with_for_update()
            )
            if (
                job is None
                or job.status in {"SUCCEEDED", "FAILED"}
                or not job.params_json.get("upload_ready")
            ):
                return False
            dataset = db.scalar(
                select(Dataset).where(
                    Dataset.id == dataset_id, Dataset.organization_id == job.organization_id
                )
            )
            if dataset is None:
                finish(job, "DATASET_MISSING")
                return False
            if job.attempt_count >= 3:
                finish(job, "RETRY_EXHAUSTED")
                return False
            next_attempt = job.params_json.get("retry_at", 0)
            if (
                isinstance(next_attempt, (int, float))
                and next_attempt > datetime.now(UTC).timestamp()
            ):
                return False
            job.attempt_count += 1
            job.status = "PROCESSING"
            job.started_at = job.started_at or datetime.now(UTC)
            job.error_code = job.error_message = None
        try:
            validate_job(db, job, dataset, storage)
        except InvalidCSV as exc:
            with db.begin():
                dataset.status = "REJECTED"
                job.params_json = {**job.params_json, "cleanup_pending": True}
                finish(job, exc.code)
        except StorageUnavailable:
            with db.begin():
                if job.attempt_count >= 3:
                    finish(job, "STORAGE_UNAVAILABLE")
                else:
                    retry_at = datetime.now(UTC).timestamp() + 5 * 2**job.attempt_count
                    job.status = "QUEUED"
                    job.params_json = {
                        **job.params_json,
                        "retry_at": retry_at,
                        "next_publish_at": retry_at,
                    }
                    job.error_code = "STORAGE_UNAVAILABLE"
                    job.error_message = "Storage is unavailable. A retry is scheduled."
            return job.status == "QUEUED"
        return False
