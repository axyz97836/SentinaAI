"""Read-only reconciliation, restricted to the disposable synthetic integration DB."""

import json

from app.config import get_settings
from app.database import database_engine
from app.models import (
    Alert,
    AuditLog,
    Case,
    CaseEvent,
    Organization,
    ScoringResult,
    Transaction,
    TransactionLabel,
)
from app.seed import ORGANIZATION_NAME
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

settings = get_settings()
assert (
    settings.app_env == "local" and settings.postgres_db == "sentinelai_ingestion_test"
)
engine = database_engine(settings.database_url)
try:
    with Session(engine) as db:
        assert (
            db.scalar(text("SELECT current_database()")) == "sentinelai_ingestion_test"
        )
        org = db.scalars(
            select(Organization).where(Organization.name == ORGANIZATION_NAME)
        ).one()
        cases = list(db.scalars(select(Case).where(Case.organization_id == org.id)))
        events_count = 0
        for case in cases:
            alert = db.get(Alert, case.alert_id)
            assert alert.organization_id == org.id and alert.status == "IN_CASE"
            events = list(
                db.scalars(
                    select(CaseEvent)
                    .where(CaseEvent.case_id == case.id)
                    .order_by(CaseEvent.created_at, CaseEvent.id)
                )
            )
            audits = list(
                db.scalars(
                    select(AuditLog).where(
                        AuditLog.resource_type == "CASE",
                        AuditLog.resource_id == case.id,
                    )
                )
            )
            assert events[0].action == "CASE_OPENED"
            assert len(events) == len(audits)
            assert sorted(e.action for e in events) == sorted(a.action for a in audits)
            assert all(
                a.organization_id == org.id
                and a.request_id
                and "note" not in a.metadata_json
                for a in audits
            )
            assert all("fictional-c-" not in str(a.metadata_json) for a in audits)
            if case.status == "CLOSED":
                assert (
                    events[-1].action == "CASE_CLOSED"
                    and case.version == 3
                    and case.closed_at
                )
                assert sum(e.action == "CASE_CLOSED" for e in events) == 1
            else:
                assert case.status == "OPEN" and case.version == 1
            events_count += len(events)
        dismissed = list(
            db.scalars(
                select(Alert).where(
                    Alert.organization_id == org.id, Alert.status == "DISMISSED"
                )
            )
        )
        for alert in dismissed:
            assert alert.dismissal_reason and alert.dismissed_by
            assert not db.scalar(select(Case.id).where(Case.alert_id == alert.id))
            audit = db.scalars(
                select(AuditLog).where(
                    AuditLog.resource_id == alert.id,
                    AuditLog.action == "ALERT_DISMISSED",
                )
            ).one()
            assert (
                audit.actor_user_id == alert.dismissed_by
                and "fictional-c-" not in str(audit.metadata_json)
            )
        transactions = db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.organization_id == org.id)
        )
        scores = db.scalar(
            select(func.count())
            .select_from(ScoringResult)
            .join(Transaction)
            .where(Transaction.organization_id == org.id)
        )
        assert transactions == scores == len(cases) + len(dismissed)
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransactionLabel)
                .join(Transaction)
                .where(Transaction.organization_id == org.id)
            )
            == 0
        )
        print(
            json.dumps(
                {
                    "transactions": transactions,
                    "cases": len(cases),
                    "closed_cases": sum(c.status == "CLOSED" for c in cases),
                    "events": events_count,
                    "dismissed": len(dismissed),
                }
            )
        )
finally:
    engine.dispose()
