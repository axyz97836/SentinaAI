from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import and_, or_, select

from app.auth.dependencies import Database, Identity, organization_record
from app.auth.errors import AuthError
from app.ingestion.storage import StorageUnavailable
from app.ingestion.validation import InvalidCSV
from app.models import Alert, Case, RuleHit, ScoringResult, Transaction
from app.scoring.schema import TransactionInput
from app.scoring.service import score_transaction

router = APIRouter(prefix="/api/v1/transactions")


@router.post("", status_code=201)
def submit(
    payload: TransactionInput,
    request: Request,
    response: Response,
    db: Database,
    principal: Identity,
) -> dict[str, object]:
    try:
        result, created = score_transaction(
            db,
            request.app.state.storage,
            principal.organization_id,
            principal.user_id,
            payload,
            source="SINGLE",
            request_id=request.state.request_id,
        )
    except InvalidCSV as exc:
        raise AuthError(409, exc.code, "Model inference could not be verified.") from None
    except StorageUnavailable:
        raise AuthError(
            503, "STORAGE_UNAVAILABLE", "Model storage is temporarily unavailable."
        ) from None
    response.status_code = 201 if created else 200
    return result


def transaction_fields(transaction: Transaction) -> dict[str, object]:
    return {
        name: getattr(transaction, name)
        for name in (
            "id",
            "external_id",
            "customer_ref",
            "occurred_at",
            "amount",
            "currency",
            "merchant_category",
            "country_code",
            "channel",
            "device_ref",
            "source",
            "ingested_at",
        )
    }


def utc(stamp: datetime) -> datetime:
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise AuthError(422, "INVALID_TIMESTAMP", "Date filters require an explicit timezone.")
    return stamp.astimezone(UTC)


@router.get("")
def list_transactions(
    db: Database,
    principal: Identity,
    cursor: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    ),
    band: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    risk_band: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, object]:
    query = (
        select(Transaction, ScoringResult)
        .join(ScoringResult)
        .where(Transaction.organization_id == principal.organization_id)
    )
    if date_from is not None:
        date_from = utc(date_from)
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        date_to = utc(date_to)
        query = query.where(Transaction.occurred_at < date_to)
    if date_from is not None and date_to is not None and date_from >= date_to:
        raise AuthError(422, "INVALID_DATE_RANGE", "Date range must be increasing.")
    if band and risk_band and band != risk_band:
        raise AuthError(422, "INVALID_FILTER", "Risk band filters disagree.")
    if band or risk_band:
        query = query.where(ScoringResult.risk_band == (band or risk_band))
    if search:
        query = query.where(
            or_(
                Transaction.external_id.contains(search, autoescape=True),
                Transaction.customer_ref.contains(search, autoescape=True),
            )
        )
    if cursor:
        try:
            stamp, identifier = cursor.split("|")
            time = utc(datetime.fromisoformat(stamp))
            value = UUID(identifier)
        except (ValueError, TypeError):
            raise AuthError(422, "INVALID_CURSOR", "Pagination cursor is invalid.") from None
        query = query.where(
            or_(
                Transaction.occurred_at < time,
                and_(Transaction.occurred_at == time, Transaction.id > value),
            )
        )
    rows = list(
        db.execute(query.order_by(Transaction.occurred_at.desc(), Transaction.id).limit(limit + 1))
    )
    return {
        "items": [
            {
                **transaction_fields(tx),
                "scoring_result_id": score.id,
                "risk_score": score.risk_score,
                "risk_band": score.risk_band,
                "model_version_id": score.model_version_id,
            }
            for tx, score in rows[:limit]
        ],
        "next_cursor": f"{rows[limit - 1][0].occurred_at.isoformat()}|{rows[limit - 1][0].id}"
        if len(rows) > limit
        else None,
    }


@router.get("/{identifier}")
def detail(identifier: UUID, db: Database, principal: Identity) -> dict[str, object]:
    transaction = organization_record(db, Transaction, identifier, principal)
    score = db.scalars(
        select(ScoringResult).where(ScoringResult.transaction_id == transaction.id)
    ).one()
    alert = db.scalar(
        select(Alert).where(
            Alert.scoring_result_id == score.id, Alert.organization_id == principal.organization_id
        )
    )
    case_id = (
        db.scalar(
            select(Case.id).where(
                Case.alert_id == alert.id, Case.organization_id == principal.organization_id
            )
        )
        if alert
        else None
    )
    hits = db.scalars(
        select(RuleHit)
        .where(RuleHit.scoring_result_id == score.id)
        .order_by(RuleHit.rule_code_snapshot)
        .limit(3)
    )
    return {
        "transaction": transaction_fields(transaction),
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
        "rule_hits": [
            {"code": hit.rule_code_snapshot, "strength": hit.strength, "details": hit.details_json}
            for hit in hits
        ],
        "alert_id": alert.id if alert else None,
        "case_id": case_id,
    }
