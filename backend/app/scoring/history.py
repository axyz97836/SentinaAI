"""Minimal prior-only rule evaluation; no rule configuration or invented defaults."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RuleDefinition, Transaction
from app.scoring.schema import TransactionInput

CODES = ("AMOUNT_OUTLIER", "HIGH_VELOCITY", "DEVICE_CHANGE")


def evaluate(
    db: Session, org: UUID, payload: TransactionInput
) -> tuple[Decimal, list[dict[str, Any]]]:
    stamp = datetime.fromisoformat(payload.occurred_at)
    prior = select(Transaction).where(
        Transaction.organization_id == org,
        Transaction.customer_ref == payload.customer_ref,
        Transaction.occurred_at < stamp,
        Transaction.external_id != payload.external_id,
    )
    definitions = {
        rule.code: rule
        for rule in db.scalars(
            select(RuleDefinition).where(
                RuleDefinition.organization_id == org, RuleDefinition.code.in_(CODES)
            )
        )
    }
    evidence: list[dict[str, Any]] = []
    for code in CODES:
        rule = definitions.get(code)
        item: dict[str, Any] = {"code": code, "status": "NOT_CONFIGURED"}
        evidence.append(item)
        if rule is None:
            continue
        item.update(definition_id=str(rule.id), version=rule.version)
        if not rule.enabled:
            item["status"] = "DISABLED"
            continue
        params = rule.parameters_json
        item["status"] = "UNSUPPORTED_PARAMETERS"
        hit: bool
        if code == "AMOUNT_OUTLIER":
            multiplier, minimum = params.get("multiplier"), params.get("min_history")
            if (
                set(params) != {"multiplier", "min_history"}
                or not isinstance(multiplier, (int, float))
                or isinstance(multiplier, bool)
                or not 1 < multiplier <= 100
                or type(minimum) is not int
                or not 1 <= minimum <= 100
            ):
                continue
            # Bounded recent same-currency history; nominal amounts are never FX converted.
            history = list(
                db.scalars(
                    prior.where(Transaction.currency == payload.currency)
                    .order_by(Transaction.occurred_at.desc(), Transaction.id)
                    .limit(100)
                )
            )
            item.update(parameters=params, history_count=len(history), history_limit=100)
            if len(history) < minimum:
                item["status"] = "MISSING_HISTORY"
                continue
            average = sum((row.amount for row in history), Decimal(0)) / len(history)
            ratio = Decimal(str(payload.amount)) / average
            item["amount_ratio"] = str(ratio.quantize(Decimal("0.000001")))
            hit = ratio > Decimal(str(multiplier))
        elif code == "HIGH_VELOCITY":
            threshold = params.get("count_threshold")
            if (
                set(params) != {"window_minutes", "count_threshold"}
                or type(params.get("window_minutes")) is not int
                or params["window_minutes"] != 10
                or type(threshold) is not int
                or not 1 <= threshold <= 1000
            ):
                continue
            # Saturation is explicit: only enough rows to decide the threshold are fetched.
            ids = list(
                db.scalars(
                    prior.with_only_columns(Transaction.id)
                    .where(Transaction.occurred_at >= stamp - timedelta(minutes=10))
                    .limit(threshold)
                )
            )
            item.update(parameters=params, prior_count=len(ids), count_capped_at=threshold)
            if not ids and db.scalar(prior.with_only_columns(Transaction.id).limit(1)) is None:
                item["status"] = "MISSING_HISTORY"
                continue
            hit = len(ids) >= threshold
        else:
            if params:
                continue
            previous = db.scalar(
                prior.order_by(Transaction.occurred_at.desc(), Transaction.id).limit(1)
            )
            item["parameters"] = {}
            if previous is None or previous.device_ref is None or payload.device_ref is None:
                item["status"] = "MISSING_HISTORY"
                continue
            hit = previous.device_ref != payload.device_ref
            item["device_changed"] = hit
        item["status"] = "HIT" if hit else "NOT_HIT"
    # Contract leaves aggregation open: any actual binary hit is 1; otherwise 0.
    # Missing/disabled rules stay explicit; the model's component weights never change.
    return Decimal(int(any(item["status"] == "HIT" for item in evidence))), evidence
