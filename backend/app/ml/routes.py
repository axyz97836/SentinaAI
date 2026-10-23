from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.auth.dependencies import Database, Identity, require_roles
from app.auth.errors import AuthError
from app.auth.service import Principal
from app.ingestion.storage import StorageUnavailable
from app.ingestion.validation import InvalidCSV
from app.ml.service import activate, metadata, request_training
from app.models import ModelVersion

router = APIRouter(prefix="/api/v1")
Admin = Annotated[Principal, Depends(require_roles("ADMIN"))]


class TrainingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    training_dataset_id: UUID


class ActivationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


@router.post("/admin/models/train", status_code=202)
def start_training(
    payload: TrainingInput, request: Request, db: Database, principal: Admin
) -> dict[str, object]:
    try:
        job = request_training(db, principal, payload.training_dataset_id, request.state.request_id)
    except InvalidCSV as exc:
        raise AuthError(422, exc.code, "Dataset is not eligible for training.") from None
    return {"job_id": job.id, "status": "QUEUED"}


@router.get("/admin/models")
def list_models(
    db: Database,
    principal: Admin,
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    query = select(ModelVersion).where(ModelVersion.organization_id == principal.organization_id)
    if cursor is not None:
        query = query.where(ModelVersion.id > cursor)
    models = list(db.scalars(query.order_by(ModelVersion.id).limit(limit + 1)))
    return {
        "items": [metadata(db, model) for model in models[:limit]],
        "next_cursor": str(models[limit - 1].id) if len(models) > limit else None,
    }


@router.post("/admin/models/{identifier}/activate")
def activate_model(
    identifier: UUID, payload: ActivationInput, request: Request, db: Database, principal: Admin
) -> dict[str, object]:
    try:
        model = activate(
            db, request.app.state.storage, principal, identifier, request.state.request_id
        )
    except InvalidCSV as exc:
        raise AuthError(409, exc.code, "Model artifact could not be verified.") from None
    except StorageUnavailable:
        raise AuthError(
            503, "STORAGE_UNAVAILABLE", "Model storage is temporarily unavailable."
        ) from None
    return metadata(db, model)


@router.get("/models/active")
def active_model(db: Database, principal: Identity) -> dict[str, object]:
    model = db.scalar(
        select(ModelVersion).where(
            ModelVersion.organization_id == principal.organization_id,
            ModelVersion.is_active.is_(True),
        )
    )
    if model is None:
        raise AuthError(409, "ACTIVE_MODEL_REQUIRED", "An admin must activate a model.")
    return metadata(db, model)
