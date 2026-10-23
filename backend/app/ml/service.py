"""Organization-scoped admission, trusted loading and atomic activation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import organization_record
from app.auth.errors import AuthError
from app.auth.service import Principal
from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import InvalidCSV
from app.ml import artifacts
from app.ml.data import check_dataset
from app.ml.training import WEIGHTS, BaselineBundle
from app.models import AuditLog, Dataset, Job, ModelVersion, Organization


def provenance(job: Job, dataset: Dataset, candidate: UUID) -> dict[str, str]:
    return {
        "organization_id": str(job.organization_id),
        "dataset_id": str(dataset.id),
        "dataset_sha256": dataset.sha256,
        "job_id": str(job.id),
        "model_id": str(candidate),
    }


def request_training(db: Session, principal: Principal, dataset_id: UUID, request_id: str) -> Job:
    db.execute(
        select(Organization.id)
        .where(Organization.id == principal.organization_id)
        .with_for_update()
    ).one()
    dataset = organization_record(db, Dataset, dataset_id, principal)
    check_dataset(dataset, principal.organization_id)
    pending = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.organization_id == principal.organization_id,
            Job.type == "MODEL_TRAIN",
            Job.status.in_(("QUEUED", "PROCESSING")),
        )
    )
    recent = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.organization_id == principal.organization_id,
            Job.type == "MODEL_TRAIN",
            Job.created_at >= datetime.now(UTC) - timedelta(minutes=15),
        )
    )
    if pending or (recent or 0) >= 3:
        raise AuthError(429, "TRAINING_LIMIT", "Training limit reached. Try later.", 60)
    job = Job(
        id=uuid4(),
        organization_id=principal.organization_id,
        requested_by=principal.user_id,
        dataset_id=dataset.id,
        type="MODEL_TRAIN",
        status="QUEUED",
        total_rows=dataset.row_count,
        params_json={"candidate_id": str(uuid4())},
    )
    db.add(job)
    db.add(
        AuditLog(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="MODEL_TRAIN_REQUESTED",
            resource_type="JOB",
            resource_id=job.id,
            metadata_json={"dataset_id": str(dataset.id)},
            request_id=request_id,
        )
    )
    return job


def load_bundle(db: Session, storage: PrivateStorage, model: ModelVersion) -> BaselineBundle:
    job = db.scalar(
        select(Job).where(
            Job.organization_id == model.organization_id,
            Job.model_version_id == model.id,
            Job.dataset_id == model.training_dataset_id,
            Job.type == "MODEL_TRAIN",
            Job.status == "SUCCEEDED",
        )
    )
    dataset = db.scalar(
        select(Dataset).where(
            Dataset.id == model.training_dataset_id,
            Dataset.organization_id == model.organization_id,
        )
    )
    if (
        job is None
        or dataset is None
        or job.params_json.get("candidate_id") != str(model.id)
        or model.artifact_key != artifacts.key(model.organization_id, model.id)
    ):
        raise InvalidCSV("ARTIFACT_UNTRUSTED")
    check_dataset(dataset, model.organization_id)
    content = artifacts.read(storage, model.organization_id, model.id)
    bundle = artifacts.unpack_verified(
        content,
        model.artifact_sha256,
        provenance(job, dataset, model.id),
        model.feature_schema_json,
    )
    if bundle.metrics != model.metrics_json or model.weight_config_json != WEIGHTS:
        raise InvalidCSV("ARTIFACT_METADATA_MISMATCH")
    return bundle


def activate(
    db: Session, storage: PrivateStorage, principal: Principal, identifier: UUID, request_id: str
) -> ModelVersion:
    db.execute(
        select(Organization.id)
        .where(Organization.id == principal.organization_id)
        .with_for_update()
    ).one()
    model = organization_record(db, ModelVersion, identifier, principal)
    load_bundle(db, storage, model)
    if model.is_active:
        return model
    db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.organization_id == principal.organization_id,
            ModelVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )
    model.is_active = True
    model.activated_at = datetime.now(UTC)
    db.add(
        AuditLog(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="MODEL_ACTIVATED",
            resource_type="MODEL",
            resource_id=model.id,
            metadata_json={"version_label": model.version_label},
            request_id=request_id,
        )
    )
    db.flush()
    return model


def metadata(db: Session, model: ModelVersion) -> dict[str, object]:
    dataset = db.scalars(
        select(Dataset).where(
            Dataset.id == model.training_dataset_id,
            Dataset.organization_id == model.organization_id,
        )
    ).one()
    return {
        "id": model.id,
        "version_label": model.version_label,
        "algorithm": model.algorithm,
        "is_active": model.is_active,
        "trained_at": model.trained_at,
        "activated_at": model.activated_at,
        "metrics": model.metrics_json,
        "feature_schema": model.feature_schema_json,
        "weights": model.weight_config_json,
        "training_dataset": {
            "id": dataset.id,
            "source_kind": dataset.source_kind,
            "schema_version": dataset.schema_version,
            "row_count": dataset.row_count,
        },
    }
