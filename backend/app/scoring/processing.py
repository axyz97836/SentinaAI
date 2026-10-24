"""Scoring results and each row's durable progress commit together."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.ingestion.service import finish
from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import MAX_ERRORS, InvalidCSV, UploadMetadata, csv_rows
from app.models import Dataset, Job, JobError, Organization, TransactionLabel
from app.scoring.schema import TransactionInput
from app.scoring.service import score_transaction, scoring_model


def score_job(db: Session, job: Job, dataset: Dataset, storage: PrivateStorage) -> None:
    UploadMetadata(
        purpose=dataset.purpose,
        source_kind=dataset.source_kind,
        license_reference=dataset.license_reference,
    )
    if dataset.schema_version != "1" or dataset.object_key != storage.key(
        job.organization_id, dataset.id
    ):
        raise InvalidCSV("DATASET_INTEGRITY_FAILED")
    with storage.read(job.organization_id, dataset.id, dataset.size_bytes, dataset.sha256) as file:
        # Preflight structural limits before any operational writes. Row errors remain independent.
        total = sum(1 for _ in csv_rows(file))
        with db.begin():
            db.refresh(job, with_for_update=True)
            if job.status in {"SUCCEEDED", "FAILED"}:
                return
            job.total_rows = dataset.row_count = total
            dataset.status = "VALIDATED"
            job.params_json = {**job.params_json, "progress_phase": "SCORING"}
        try:
            with db.begin():
                db.execute(
                    select(Organization.id)
                    .where(Organization.id == job.organization_id)
                    .with_for_update()
                ).one()
                # Pin the verified active version durably, including across retries.
                model = scoring_model(db, storage, job.organization_id, job.model_version_id)
                job.model_version_id = model.id
            completed = job.processed_rows + job.failed_rows
            with db.begin():
                stored = (
                    db.scalar(
                        select(func.count()).select_from(JobError).where(JobError.job_id == job.id)
                    )
                    or 0
                )
            for number, row, code in csv_rows(file):
                if number <= completed:
                    continue
                with db.begin():
                    db.refresh(job, with_for_update=True)
                    if job.status in {"SUCCEEDED", "FAILED"}:
                        return
                    if row is not None:
                        try:
                            with db.begin_nested():
                                label = row.pop("fraud_label", None)
                                result, _ = score_transaction(
                                    db,
                                    storage,
                                    job.organization_id,
                                    job.requested_by,
                                    TransactionInput.model_validate(row),
                                    source="CSV",
                                    model=model,
                                )
                                if label is not None:
                                    transaction_id = UUID(str(result["transaction_id"]))
                                    db.execute(
                                        insert(TransactionLabel)
                                        .values(
                                            transaction_id=transaction_id,
                                            fraud_label=label == "1",
                                            label_source=dataset.source_kind,
                                        )
                                        .on_conflict_do_nothing(
                                            index_elements=[TransactionLabel.transaction_id]
                                        )
                                    )
                                    existing = db.get(TransactionLabel, transaction_id)
                                    if (
                                        existing is None
                                        or existing.fraud_label != (label == "1")
                                        or existing.label_source != dataset.source_kind
                                    ):
                                        raise AuthError(
                                            409,
                                            "DUPLICATE_LABEL_CONFLICT",
                                            "Existing label differs.",
                                        )
                        except AuthError as exc:
                            if exc.code not in {
                                "DUPLICATE_TRANSACTION_CONFLICT",
                                "DUPLICATE_LABEL_CONFLICT",
                            }:
                                raise
                            code = exc.code
                    if code:
                        job.failed_rows += 1
                        if stored < MAX_ERRORS:
                            db.add(
                                JobError(
                                    job_id=job.id,
                                    row_number=number,
                                    code=code,
                                    summary="Row is invalid or conflicts with stored data.",
                                )
                            )
                            stored += 1
                    else:
                        job.processed_rows += 1
            with db.begin():
                finish(job)
                if job.failed_rows:
                    job.error_message = "Completed with row errors."
        except InvalidCSV as exc:
            # Model failure does not invalidate or delete an otherwise valid source CSV.
            raise AuthError(409, exc.code, "Model inference could not be verified.") from None
