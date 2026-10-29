from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.auth.service import Principal
from app.investigations.schema import AlertStatus, CaseStatus, RiskBand
from app.investigations.service import case_record, scoped_alerts, scoped_cases
from app.models import Alert, Case, CaseEvent, ScoringResult, Transaction
from app.scoring.explanations import explanation
from app.scoring.routes import transaction_fields


def parse_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        stamp, identifier = value.split("|")
        time = datetime.fromisoformat(stamp)
        if time.tzinfo is None or time.utcoffset() is None:
            raise ValueError("Timezone required")
        return time.astimezone(UTC), UUID(identifier)
    except (ValueError, OverflowError):
        raise AuthError(422, "INVALID_CURSOR", "Pagination cursor is invalid.") from None


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=100)
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered(self) -> "Page":
        if self.date_from is not None and self.date_to is not None:
            if self.date_from >= self.date_to:
                raise ValueError("Date range must be increasing")
        return self


class AlertFilters(Page):
    status: AlertStatus | None = None
    risk_band: RiskBand | None = None


class CaseFilters(Page):
    status: CaseStatus | None = None


def alert_view(alert: Alert) -> dict[str, Any]:
    return {
        name: getattr(alert, name)
        for name in (
            "id",
            "scoring_result_id",
            "status",
            "reason_summary",
            "dismissal_reason",
            "dismissed_by",
            "created_at",
            "updated_at",
        )
    }


def case_view(case: Case) -> dict[str, Any]:
    return {
        name: getattr(case, name)
        for name in (
            "id",
            "alert_id",
            "created_by",
            "assigned_to",
            "status",
            "resolution",
            "resolution_note",
            "created_at",
            "updated_at",
            "closed_at",
            "version",
        )
    }


def event_view(event: CaseEvent) -> dict[str, Any]:
    return {
        name: getattr(event, name)
        for name in (
            "id",
            "case_id",
            "actor_user_id",
            "action",
            "previous_status",
            "new_status",
            "note",
            "created_at",
        )
    }


def list_alerts(db: Session, principal: Principal, filters: AlertFilters) -> dict[str, Any]:
    query = (
        scoped_alerts(principal.organization_id)
        .add_columns(ScoringResult, Transaction, Case.id)
        .outerjoin(Case, Case.alert_id == Alert.id)
        .where(or_(Case.id.is_(None), Case.organization_id == principal.organization_id))
    )
    if filters.status is not None:
        query = query.where(Alert.status == filters.status)
    if filters.risk_band is not None:
        query = query.where(ScoringResult.risk_band == filters.risk_band)
    if filters.date_from is not None:
        query = query.where(Alert.created_at >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Alert.created_at < filters.date_to)
    if cursor := parse_cursor(filters.cursor):
        stamp, identifier = cursor
        query = query.where(
            or_(Alert.created_at < stamp, and_(Alert.created_at == stamp, Alert.id > identifier))
        )
    rows = list(
        db.execute(query.order_by(Alert.created_at.desc(), Alert.id).limit(filters.limit + 1))
    )
    items = [
        {
            **alert_view(alert),
            "transaction_id": tx.id,
            "external_id": tx.external_id,
            "customer_ref": tx.customer_ref,
            "occurred_at": tx.occurred_at,
            "risk_score": score.risk_score,
            "risk_band": score.risk_band,
            "case_id": case_id,
        }
        for alert, score, tx, case_id in rows[: filters.limit]
    ]
    return {
        "items": items,
        "next_cursor": (
            f"{rows[filters.limit - 1][0].created_at.isoformat()}|{rows[filters.limit - 1][0].id}"
        )
        if len(rows) > filters.limit
        else None,
    }


def list_cases(db: Session, principal: Principal, filters: CaseFilters) -> dict[str, Any]:
    query = scoped_cases(principal.organization_id)
    if filters.status is not None:
        query = query.where(Case.status == filters.status)
    if filters.date_from is not None:
        query = query.where(Case.updated_at >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Case.updated_at < filters.date_to)
    if cursor := parse_cursor(filters.cursor):
        stamp, identifier = cursor
        query = query.where(
            or_(Case.updated_at < stamp, and_(Case.updated_at == stamp, Case.id > identifier))
        )
    rows = list(
        db.scalars(query.order_by(Case.updated_at.desc(), Case.id).limit(filters.limit + 1))
    )
    return {
        "items": [case_view(case) for case in rows[: filters.limit]],
        "next_cursor": (
            f"{rows[filters.limit - 1].updated_at.isoformat()}|{rows[filters.limit - 1].id}"
        )
        if len(rows) > filters.limit
        else None,
    }


def detail(
    db: Session,
    principal: Principal,
    identifier: UUID,
    events_limit: int,
    events_cursor: str | None,
) -> dict[str, Any]:
    # Share-lock keeps the case and timeline consistent with concurrent note/closure writes.
    case = case_record(db, principal, identifier, shared=True)
    alert, score, tx = db.execute(
        scoped_alerts(principal.organization_id)
        .add_columns(ScoringResult, Transaction)
        .where(Alert.id == case.alert_id)
    ).one()
    query = select(CaseEvent).where(CaseEvent.case_id == case.id)
    if cursor := parse_cursor(events_cursor):
        stamp, event_id = cursor
        query = query.where(
            or_(
                CaseEvent.created_at > stamp,
                and_(CaseEvent.created_at == stamp, CaseEvent.id > event_id),
            )
        )
    events = list(
        db.scalars(query.order_by(CaseEvent.created_at, CaseEvent.id).limit(events_limit + 1))
    )
    return {
        "case": case_view(case),
        "alert": alert_view(alert),
        "transaction": transaction_fields(tx),
        "score": {
            name: getattr(score, name)
            for name in (
                "id",
                "model_version_id",
                "risk_score",
                "risk_band",
                "supervised_probability",
                "anomaly_percentile",
                "rule_signal",
                "explanation_status",
                "explanation_json",
                "settings_snapshot_json",
                "latency_ms",
                "scored_at",
            )
        },
        "explanation": explanation(db, principal, tx.id),
        "events": [event_view(event) for event in events[:events_limit]],
        "next_events_cursor": (
            f"{events[events_limit - 1].created_at.isoformat()}|{events[events_limit - 1].id}"
        )
        if len(events) > events_limit
        else None,
    }
