"""Read only the evidence persisted with the original score; never re-explain on GET."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import organization_record
from app.auth.service import Principal
from app.models import RuleHit, ScoringResult, Transaction

CAVEAT = "This score is a screening signal, not proof of fraud or a calibrated fraud probability."


def explanation(db: Session, principal: Principal, identifier: UUID) -> dict[str, object]:
    transaction = organization_record(db, Transaction, identifier, principal)
    score = db.scalars(
        select(ScoringResult).where(ScoringResult.transaction_id == transaction.id)
    ).one()
    stored = score.explanation_json
    weights = stored["weights"]
    values = {
        "supervised": score.supervised_probability,
        "anomaly": score.anomaly_percentile,
        "rules": score.rule_signal,
    }
    hits = db.scalars(
        select(RuleHit)
        .where(RuleHit.scoring_result_id == score.id)
        .order_by(RuleHit.rule_code_snapshot)
        .limit(3)
    )
    return {
        "transaction_id": transaction.id,
        "scoring_result_id": score.id,
        "model_version_id": score.model_version_id,
        "risk_score": score.risk_score,
        "risk_band": score.risk_band,
        "supervised_probability": score.supervised_probability,
        "anomaly_percentile": score.anomaly_percentile,
        "rule_signal": score.rule_signal,
        "weights": weights,
        "component_contributions": {
            key: {
                "value": value,
                "weight": weights[key],
                "risk_points": Decimal(100) * value * Decimal(str(weights[key])),
            }
            for key, value in values.items()
        },
        "rule_evaluations": stored.get("rules", []),
        "rule_hits": [
            {"code": hit.rule_code_snapshot, "strength": hit.strength, "details": hit.details_json}
            for hit in hits
        ],
        "supervised_attribution": stored.get(
            "supervised_attribution",
            {
                "available": False,
                "method": None,
                "top_features": [],
                "reason": "NOT_RECORDED_AT_SCORING_TIME",
            },
        ),
        "settings_snapshot": score.settings_snapshot_json,
        "explanation_status": score.explanation_status,
        "caveat": CAVEAT,
        "limitations": [
            "Supervised attribution explains only the classifier, not the composite risk score.",
            "Anomaly percentile is relative to the training reference, not a fraud probability.",
            "Missing rule history is not evidence of safety. "
            "Synthetic evaluation does not establish calibration.",
        ],
    }
