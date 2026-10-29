"""Caller owns the commit: state, timeline and redacted audit are one transaction."""

from datetime import UTC, datetime
from typing import Any, Never
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.auth.service import Principal
from app.investigations.schema import AddNote, DismissAlert, OpenCase, ResolveCase, ReviewCase
from app.models import Alert, AuditLog, Case, CaseEvent, ModelVersion, ScoringResult, Transaction


def scoped_alerts(org: UUID) -> Select[Alert]:
    return (
        select(Alert)
        .join(ScoringResult, ScoringResult.id == Alert.scoring_result_id)
        .join(Transaction, Transaction.id == ScoringResult.transaction_id)
        .join(ModelVersion, ModelVersion.id == ScoringResult.model_version_id)
        .where(
            Alert.organization_id == org,
            Transaction.organization_id == org,
            ModelVersion.organization_id == org,
        )
    )


def alert_record(db: Session, principal: Principal, identifier: UUID) -> Alert:
    alert = db.scalar(
        scoped_alerts(principal.organization_id)
        .where(Alert.id == identifier)
        .with_for_update(of=Alert)
        .execution_options(populate_existing=True)
    )
    if alert is None:
        raise AuthError(404, "NOT_FOUND", "Record is not available.")
    return alert


def scoped_cases(org: UUID) -> Select[Case]:
    return (
        select(Case)
        .join(Alert, Alert.id == Case.alert_id)
        .join(ScoringResult, ScoringResult.id == Alert.scoring_result_id)
        .join(Transaction, Transaction.id == ScoringResult.transaction_id)
        .join(ModelVersion, ModelVersion.id == ScoringResult.model_version_id)
        .where(
            Case.organization_id == org,
            Alert.organization_id == org,
            Transaction.organization_id == org,
            ModelVersion.organization_id == org,
        )
    )


def case_record(
    db: Session, principal: Principal, identifier: UUID, *, shared: bool = False
) -> Case:
    case = db.scalar(
        scoped_cases(principal.organization_id)
        .where(Case.id == identifier)
        .with_for_update(of=Case, read=shared)
        .execution_options(populate_existing=True)
    )
    if case is None:
        raise AuthError(404, "NOT_FOUND", "Record is not available.")
    return case


def conflict() -> Never:
    raise AuthError(409, "INVESTIGATION_CONFLICT", "Record changed. Refresh and retry.")


def audit(
    db: Session,
    principal: Principal,
    action: str,
    resource: str,
    identifier: UUID,
    request_id: str,
    metadata: dict[str, Any],
) -> None:
    db.add(
        AuditLog(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            action=action,
            resource_type=resource,
            resource_id=identifier,
            request_id=request_id,
            metadata_json=metadata,
        )
    )


def case_event(
    db: Session,
    principal: Principal,
    case: Case,
    action: str,
    previous: str | None,
    note: str | None,
    request_id: str,
) -> CaseEvent:
    event = CaseEvent(
        id=uuid4(),
        case_id=case.id,
        actor_user_id=principal.user_id,
        action=action,
        previous_status=previous,
        new_status=case.status,
        note=note,
        created_at=case.updated_at,
    )
    db.add(event)
    audit(
        db,
        principal,
        action,
        "CASE",
        case.id,
        request_id,
        {
            "previous_status": previous,
            "status": case.status,
            "version": case.version,
            "resolution": case.resolution,
            "note_present": note is not None,
        },
    )
    db.flush()
    return event


def dismiss(
    db: Session, principal: Principal, identifier: UUID, payload: DismissAlert, request_id: str
) -> Alert:
    alert = alert_record(db, principal, identifier)
    if alert.status != "NEW":
        conflict()
    alert.status = "DISMISSED"
    alert.dismissal_reason, alert.dismissed_by = payload.reason, principal.user_id
    alert.updated_at = datetime.now(UTC)
    audit(
        db,
        principal,
        "ALERT_DISMISSED",
        "ALERT",
        alert.id,
        request_id,
        {"previous_status": "NEW", "status": "DISMISSED", "reason_present": True},
    )
    db.flush()
    return alert


def open_case(
    db: Session, principal: Principal, identifier: UUID, payload: OpenCase, request_id: str
) -> tuple[Case, bool]:
    alert = alert_record(db, principal, identifier)
    existing = db.scalar(select(Case).where(Case.alert_id == alert.id))
    if existing is not None:
        if existing.organization_id != principal.organization_id:
            raise AuthError(404, "NOT_FOUND", "Record is not available.")
        opened = db.scalar(
            select(CaseEvent)
            .where(CaseEvent.case_id == existing.id, CaseEvent.action == "CASE_OPENED")
            .order_by(CaseEvent.created_at, CaseEvent.id)
            .limit(1)
        )
        if alert.status != "IN_CASE" or opened is None or opened.note != payload.note:
            conflict()
        return existing, False
    if alert.status != "NEW":
        conflict()
    stamp = datetime.now(UTC)
    case = Case(
        id=uuid4(),
        organization_id=principal.organization_id,
        alert_id=alert.id,
        created_by=principal.user_id,
        status="OPEN",
        version=1,
        created_at=stamp,
        updated_at=stamp,
    )
    alert.status, alert.updated_at = "IN_CASE", stamp
    db.add(case)
    db.flush()
    case_event(db, principal, case, "CASE_OPENED", None, payload.note, request_id)
    return case, True


def review(
    db: Session, principal: Principal, identifier: UUID, payload: ReviewCase, request_id: str
) -> Case:
    case = case_record(db, principal, identifier)
    if case.status != "OPEN" or case.version != payload.version:
        conflict()
    case.status, case.version = "IN_REVIEW", case.version + 1
    case.updated_at = datetime.now(UTC)
    case_event(db, principal, case, "STATUS_CHANGED", "OPEN", payload.note, request_id)
    return case


def add_note(
    db: Session, principal: Principal, identifier: UUID, payload: AddNote, request_id: str
) -> CaseEvent:
    case = case_record(db, principal, identifier)
    if case.status == "CLOSED":
        conflict()
    case.updated_at = datetime.now(UTC)
    return case_event(db, principal, case, "NOTE_ADDED", case.status, payload.note, request_id)


def resolve(
    db: Session, principal: Principal, identifier: UUID, payload: ResolveCase, request_id: str
) -> Case:
    case = case_record(db, principal, identifier)
    if case.status == "CLOSED":
        if (
            case.resolution == payload.resolution
            and case.resolution_note == payload.resolution_note
            and case.version == payload.version + 1
        ):
            return case
        conflict()
    if case.status != "IN_REVIEW" or case.version != payload.version:
        conflict()
    case.status, case.version = "CLOSED", case.version + 1
    case.resolution, case.resolution_note = payload.resolution, payload.resolution_note
    case.closed_at = case.updated_at = datetime.now(UTC)
    case_event(db, principal, case, "CASE_CLOSED", "IN_REVIEW", payload.resolution_note, request_id)
    return case
