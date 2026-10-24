from uuid import UUID

import anyio
from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.auth.dependencies import Database, Identity, organization_record, service
from app.auth.errors import AuthError
from app.ingestion.multipart import upload_form
from app.ingestion.service import accept_upload
from app.ingestion.validation import (
    MAX_ERRORS,
    InvalidCSV,
    UploadMetadata,
    safe_filename,
    validate_csv,
)
from app.models import Job, JobError

router = APIRouter(prefix="/api/v1")


@router.post("/ingestions", status_code=202)
async def ingest(request: Request, principal: Identity) -> dict[str, object]:
    async with upload_form(request) as form:
        try:
            items = form.multi_items()
            if len(items) != len(form) or set(form) - {
                "file",
                "purpose",
                "source_kind",
                "license_reference",
            }:
                raise InvalidCSV("INVALID_METADATA")
            metadata = UploadMetadata.model_validate({k: v for k, v in items if k != "file"})
            if metadata.purpose == "TRAINING" and principal.role != "ADMIN":
                raise AuthError(403, "FORBIDDEN", "Only administrators can upload training data.")
            file = form.get("file")
            if not isinstance(file, UploadFile) or not file.filename or not file.size:
                raise InvalidCSV("CSV_REQUIRED")
            filename = safe_filename(file.filename)
            if file.content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
                raise AuthError(
                    415, "CSV_REQUIRED", "The uploaded file must have a CSV media type."
                )
            # Check headers before storage; the worker validates rows.
            await anyio.to_thread.run_sync(lambda: list(validate_csv(file.file, headers_only=True)))
            job_id, dataset_id = await anyio.to_thread.run_sync(
                accept_upload,
                service(request).sessions,
                request.app.state.storage,
                principal,
                metadata,
                file.file,
                filename,
                file.size,
                request.state.request_id,
            )
        except (InvalidCSV, ValidationError) as exc:
            code = exc.code if isinstance(exc, InvalidCSV) else "INVALID_METADATA"
            raise AuthError(
                422, code, "CSV or upload metadata does not satisfy the contract."
            ) from None
    # The lifespan publisher reads the committed job; broker outages cannot lose admission.
    return {"job_id": job_id, "dataset_id": dataset_id, "status": "QUEUED"}


@router.get("/jobs/{identifier}")
def job_status(identifier: UUID, db: Database, principal: Identity) -> dict[str, object]:
    job = organization_record(db, Job, identifier, principal)
    errors = db.scalars(
        select(JobError)
        .where(JobError.job_id == job.id)
        .order_by(JobError.row_number, JobError.id)
        .limit(MAX_ERRORS)
    )
    return {
        "job_id": job.id,
        "dataset_id": job.dataset_id,
        "model_version_id": job.model_version_id,
        "type": job.type,
        "status": job.status,
        "total_rows": job.total_rows,
        "processed_rows": job.processed_rows,
        "failed_rows": job.failed_rows,
        "attempt_count": job.attempt_count,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "cleanup_pending": bool(job.params_json.get("cleanup_pending")),
        "cleanup_error_code": job.params_json.get("cleanup_error_code"),
        "errors": [
            {"row_number": error.row_number, "code": error.code, "summary": error.summary}
            for error in errors
        ],
        "has_output": job.status == "SUCCEEDED"
        and (
            job.type == "MODEL_TRAIN"
            and job.model_version_id is not None
            or job.params_json.get("progress_phase") == "SCORING"
            and job.processed_rows > 0
        ),
        "progress_phase": job.params_json.get("progress_phase", "VALIDATION")
        if job.type == "CSV_IMPORT"
        else "TRAINING"
        if job.type == "MODEL_TRAIN"
        else None,
        "completed_with_row_errors": job.status == "SUCCEEDED" and job.failed_rows > 0,
    }
