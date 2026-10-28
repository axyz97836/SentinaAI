"""Versioned risk configuration shares scoring's organization lock and audit transaction."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.auth.service import Principal
from app.models import AuditLog, Organization, RiskSettings, RuleDefinition
from app.scoring.rules import validate_parameters

THRESHOLDS = ("medium_threshold", "high_threshold", "critical_threshold", "alert_threshold")


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    medium_threshold: int = Field(gt=0, le=100)
    high_threshold: int = Field(gt=0, le=100)
    critical_threshold: int = Field(gt=0, le=100)
    alert_threshold: int = Field(ge=0, le=100)
    version: int = Field(ge=1, lt=2147483647)

    @model_validator(mode="after")
    def ordered(self) -> "SettingsUpdate":
        if not self.medium_threshold < self.high_threshold < self.critical_threshold:
            raise ValueError("Thresholds must be strictly increasing")
        return self


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    enabled: bool | None = None
    parameters_json: dict[str, Any] | None = None
    version: int = Field(ge=1, lt=2147483647)

    @model_validator(mode="after")
    def changes(self) -> "RuleUpdate":
        changed = self.model_fields_set - {"version"}
        if not changed or any(getattr(self, key) is None for key in changed):
            raise ValueError("Supply enabled or parameters_json; explicit null is invalid")
        return self


def settings_record(db: Session, org: UUID) -> RiskSettings:
    settings = db.scalar(
        select(RiskSettings)
        .where(RiskSettings.organization_id == org)
        .execution_options(populate_existing=True)
    )
    if settings is None:
        raise AuthError(
            409, "RISK_SETTINGS_REQUIRED", "Organization risk settings are unavailable."
        )
    return settings


def settings_view(settings: RiskSettings) -> dict[str, Any]:
    return {
        name: getattr(settings, name)
        for name in (*THRESHOLDS, "version", "updated_at", "updated_by")
    }


def rule_view(rule: RuleDefinition) -> dict[str, Any]:
    try:
        parameters = validate_parameters(rule.code, rule.parameters_json)
    except (ValueError, ValidationError):
        parameters = None
    return {
        "id": rule.id,
        "code": rule.code,
        "enabled": rule.enabled,
        "parameters_json": parameters,
        "configuration_status": "SUPPORTED" if parameters is not None else "UNSUPPORTED",
        "version": rule.version,
        "updated_at": rule.updated_at,
    }


def lock_configuration(db: Session, principal: Principal) -> None:
    if principal.role != "ADMIN":
        raise AuthError(403, "FORBIDDEN", "Only administrators can edit risk configuration.")
    db.execute(
        select(Organization.id)
        .where(Organization.id == principal.organization_id)
        .with_for_update()
    ).one()


def check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise AuthError(
            409, "CONFIGURATION_VERSION_CONFLICT", "Configuration changed. Reload and retry."
        )


def update_settings(
    db: Session, principal: Principal, payload: SettingsUpdate, request_id: str
) -> RiskSettings:
    lock_configuration(db, principal)
    settings = settings_record(db, principal.organization_id)
    check_version(settings.version, payload.version)
    before = {name: getattr(settings, name) for name in (*THRESHOLDS, "version")}
    values = payload.model_dump(exclude={"version"})
    if all(getattr(settings, key) == value for key, value in values.items()):
        return settings
    for key, value in values.items():
        setattr(settings, key, value)
    settings.version += 1
    settings.updated_by, settings.updated_at = principal.user_id, datetime.now(UTC)
    db.add(
        AuditLog(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="RISK_SETTINGS_UPDATED",
            resource_type="RISK_SETTINGS",
            resource_id=principal.organization_id,
            request_id=request_id,
            metadata_json={"before": before, "after": {**values, "version": settings.version}},
        )
    )
    db.flush()
    return settings


def update_rule(
    db: Session, principal: Principal, identifier: UUID, payload: RuleUpdate, request_id: str
) -> RuleDefinition:
    lock_configuration(db, principal)
    rule = db.scalar(
        select(RuleDefinition)
        .where(
            RuleDefinition.id == identifier,
            RuleDefinition.organization_id == principal.organization_id,
        )
        .execution_options(populate_existing=True)
    )
    if rule is None:
        raise AuthError(404, "NOT_FOUND", "Record is not available.")
    check_version(rule.version, payload.version)
    try:
        parameters = validate_parameters(
            rule.code,
            payload.parameters_json
            if payload.parameters_json is not None
            else rule.parameters_json,
        )
    except (ValueError, ValidationError):
        raise AuthError(
            422, "INVALID_RULE_PARAMETERS", "Rule parameters do not satisfy the supported contract."
        ) from None
    enabled = rule.enabled if payload.enabled is None else payload.enabled
    if enabled == rule.enabled and parameters == rule.parameters_json:
        return rule
    # Unsupported old dictionaries are never echoed into audit logs or API responses.
    before = {
        key: value
        for key, value in rule_view(rule).items()
        if key in {"enabled", "parameters_json", "version", "configuration_status"}
    }
    rule.enabled, rule.parameters_json = enabled, parameters
    rule.version += 1
    rule.updated_at = datetime.now(UTC)
    db.add(
        AuditLog(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action="RULE_UPDATED",
            resource_type="RULE",
            resource_id=rule.id,
            request_id=request_id,
            metadata_json={
                "code": rule.code,
                "before": before,
                "after": {
                    "enabled": enabled,
                    "parameters_json": parameters,
                    "version": rule.version,
                },
            },
        )
    )
    db.flush()
    return rule
