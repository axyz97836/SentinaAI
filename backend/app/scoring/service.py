"""One transaction boundary for direct requests and durable CSV rows."""

from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import InvalidCSV
from app.ml.service import load_bundle
from app.ml.training import BaselineBundle
from app.models import (
    Alert,
    AuditLog,
    ModelVersion,
    Organization,
    RiskSettings,
    RuleHit,
    ScoringResult,
    Transaction,
)
from app.scoring.calculation import band, component, composite
from app.scoring.history import evaluate
from app.scoring.schema import TransactionInput

CAVEAT = (
    "Composite risk is a screening signal, not proof of fraud or a calibrated fraud probability."
)


@dataclass(frozen=True)
class ScoringModel:
    id: UUID
    organization_id: UUID
    weights: dict[str, float]
    bundle: BaselineBundle


def scoring_model(
    db: Session, storage: PrivateStorage, org: UUID, pinned: UUID | None = None
) -> ScoringModel:
    query = select(ModelVersion).where(ModelVersion.organization_id == org)
    model = db.scalar(
        query.where(ModelVersion.id == pinned)
        if pinned
        else query.where(ModelVersion.is_active.is_(True))
    )
    if model is None or model.activated_at is None:
        raise AuthError(
            409, "ACTIVE_MODEL_REQUIRED", "An admin must activate a model before scoring."
        )
    return ScoringModel(
        model.id, org, dict(model.weight_config_json), load_bundle(db, storage, model)
    )


def summary(db: Session, transaction_id: UUID) -> dict[str, object]:
    result = db.scalars(
        select(ScoringResult).where(ScoringResult.transaction_id == transaction_id)
    ).one()
    alert = db.scalar(select(Alert.id).where(Alert.scoring_result_id == result.id))
    return {
        "transaction_id": transaction_id,
        "scoring_result_id": result.id,
        "model_version_id": result.model_version_id,
        "risk_score": result.risk_score,
        "risk_band": result.risk_band,
        "alert_id": alert,
    }


def score_transaction(
    db: Session,
    storage: PrivateStorage,
    org: UUID,
    actor: UUID,
    payload: TransactionInput,
    *,
    source: Literal["SINGLE", "CSV"],
    request_id: str | None = None,
    model: ScoringModel | None = None,
) -> tuple[dict[str, object], bool]:
    """Caller commits; any exception must roll back this entire operation."""
    started = perf_counter()
    # shortcut: serialize scoring per demo organization, revisit after measured contention.
    # Matches activation/admission lock order and makes prior-history reads consistent.
    db.execute(select(Organization.id).where(Organization.id == org).with_for_update()).one()
    identifier = db.scalar(
        insert(Transaction)
        .values(id=uuid4(), organization_id=org, source=source, **payload.values())
        .on_conflict_do_nothing(
            index_elements=[Transaction.organization_id, Transaction.external_id]
        )
        .returning(Transaction.id)
    )
    if identifier is None:
        existing = db.scalars(
            select(Transaction).where(
                Transaction.organization_id == org, Transaction.external_id == payload.external_id
            )
        ).one()
        if any(getattr(existing, key) != value for key, value in payload.values().items()):
            raise AuthError(
                409,
                "DUPLICATE_TRANSACTION_CONFLICT",
                "External ID already has different transaction data.",
            )
        return summary(db, existing.id), False
    selected = model or scoring_model(db, storage, org)
    if selected.organization_id != org:
        raise InvalidCSV("ARTIFACT_UNTRUSTED")
    probabilities, percentiles = selected.bundle.components([payload.row()])
    if probabilities.shape != (1,) or percentiles.shape != (1,):
        raise InvalidCSV("MODEL_OUTPUT_INVALID")
    supervised, anomaly = component(float(probabilities[0])), component(float(percentiles[0]))
    rules, evidence = evaluate(db, org, payload)
    settings = db.scalar(select(RiskSettings).where(RiskSettings.organization_id == org))
    if settings is None:
        raise AuthError(
            409, "RISK_SETTINGS_REQUIRED", "Organization risk settings are unavailable."
        )
    snapshot = {
        name: getattr(settings, name)
        for name in (
            "medium_threshold",
            "high_threshold",
            "critical_threshold",
            "alert_threshold",
            "version",
        )
    }
    risk_score = composite(supervised, anomaly, rules, selected.weights)
    result = ScoringResult(
        id=uuid4(),
        transaction_id=identifier,
        model_version_id=selected.id,
        supervised_probability=supervised,
        anomaly_percentile=anomaly,
        rule_signal=rules,
        risk_score=risk_score,
        risk_band=band(risk_score, snapshot),
        explanation_status="PARTIAL",
        explanation_json={
            "caveat": CAVEAT,
            "rules": evidence,
            "weights": selected.weights,
            "rule_aggregation": "any_evaluated_binary_hit",
            "model_features": "Static Phase 5 features; detailed attribution unavailable.",
            "rounding": "six_decimal_components_then_integer_half_even",
        },
        # Immutable result: measure validation/locking/inference up to result construction.
        settings_snapshot_json=snapshot,
        latency_ms=max(0, round((perf_counter() - started) * 1000)),
    )
    db.add(result)
    db.flush()
    for item in evidence:
        if item["status"] == "HIT":
            db.add(
                RuleHit(
                    scoring_result_id=result.id,
                    rule_definition_id=UUID(item["definition_id"]),
                    rule_code_snapshot=item["code"],
                    strength=1,
                    details_json=item,
                )
            )
    if risk_score >= settings.alert_threshold:
        db.add(
            Alert(
                organization_id=org,
                scoring_result_id=result.id,
                status="NEW",
                reason_summary=(
                    "This transaction crossed the configured composite risk threshold. "
                    "Review the stored component and rule evidence; this is not proof of fraud."
                ),
            )
        )
    db.add(
        AuditLog(
            organization_id=org,
            actor_user_id=actor,
            action="TRANSACTION_SCORED",
            resource_type="TRANSACTION",
            resource_id=identifier,
            metadata_json={"model_version_id": str(selected.id), "source": source},
            request_id=request_id,
        )
    )
    db.flush()
    return summary(db, identifier), True
