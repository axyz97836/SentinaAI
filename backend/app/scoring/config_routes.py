from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.auth.dependencies import Database, require_roles
from app.auth.service import Principal
from app.models import AuditLog, ModelVersion, RuleDefinition
from app.scoring.configuration import (
    RuleUpdate,
    SettingsUpdate,
    rule_view,
    settings_record,
    settings_view,
    update_rule,
    update_settings,
)

router = APIRouter(prefix="/api/v1/admin")
Admin = Annotated[Principal, Depends(require_roles("ADMIN"))]


@router.get("/settings")
def configuration(db: Database, principal: Admin) -> dict[str, object]:
    settings = settings_record(db, principal.organization_id)
    rules = db.scalars(
        select(RuleDefinition)
        .where(RuleDefinition.organization_id == principal.organization_id)
        .order_by(RuleDefinition.code)
        .limit(3)
    )
    model = db.scalar(
        select(ModelVersion).where(
            ModelVersion.organization_id == principal.organization_id,
            ModelVersion.is_active.is_(True),
        )
    )
    events = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.organization_id == principal.organization_id,
            AuditLog.action.in_(("RULE_UPDATED", "RISK_SETTINGS_UPDATED")),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(20)
    )
    return {
        **settings_view(settings),
        "rules": [rule_view(rule) for rule in rules],
        "active_model": {"id": model.id, "version_label": model.version_label} if model else None,
        "audit_summary": [
            {
                "id": event.id,
                "action": event.action,
                "actor_user_id": event.actor_user_id,
                "resource_id": event.resource_id,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@router.patch("/settings")
def edit_settings(
    payload: SettingsUpdate, request: Request, db: Database, principal: Admin
) -> dict[str, object]:
    return settings_view(update_settings(db, principal, payload, request.state.request_id))


@router.patch("/rules/{identifier}")
def edit_rule(
    identifier: UUID, payload: RuleUpdate, request: Request, db: Database, principal: Admin
) -> dict[str, object]:
    return rule_view(update_rule(db, principal, identifier, payload, request.state.request_id))
