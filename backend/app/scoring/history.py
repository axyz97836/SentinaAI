"""Minimal prior-only rule evaluation; no rule configuration or invented defaults."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RuleDefinition, Transaction
from app.scoring.rules import validate_parameters
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
        item["status"] = "UNSUPPORTED_PARAMETERS"
        try:
            params = validate_parameters(code, rule.parameters_json)
        except ValueError:
            continue
        item["parameters"] = params
        hit: bool
        if code == "AMOUNT_OUTLIER":
            multiplier, minimum = params["multiplier"], params["min_history"]
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
            item.update(
                observed_amount=str(payload.amount),
                currency=payload.currency,
                historical_mean=str(average),
                threshold_amount=str(average * Decimal(str(multiplier))),
            )
            hit = ratio > Decimal(str(multiplier))
        elif code == "HIGH_VELOCITY":
            threshold = params["count_threshold"]
            try:
                window_start = stamp - timedelta(minutes=10)
            except OverflowError:
                window_start = datetime.min.replace(tzinfo=stamp.tzinfo)
            # Indexed ten-minute range, one aggregate scalar; no unbounded row materialization.
            count = (
                db.scalar(
                    prior.with_only_columns(func.count(Transaction.id)).where(
                        Transaction.occurred_at >= window_start
                    )
                )
                or 0
            )
            item.update(
                prior_count=count,
                window_start=window_start.isoformat(),
                window_end=stamp.isoformat(),
            )
            if not count and db.scalar(prior.with_only_columns(Transaction.id).limit(1)) is None:
                item["status"] = "MISSING_HISTORY"
                continue
            hit = count >= threshold
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
        item["reason"] = {
            "AMOUNT_OUTLIER": "Amount exceeds the configured historical multiplier."
            if hit
            else "Amount does not exceed the configured historical multiplier.",
            "HIGH_VELOCITY": "Prior transaction count meets the configured threshold."
            if hit
            else "Prior transaction count is below the configured threshold.",
            "DEVICE_CHANGE": "Device differs from the preceding eligible transaction."
            if hit
            else "Device matches the preceding eligible transaction.",
        }[code]
    # Contract leaves aggregation open: any actual binary hit is 1; otherwise 0.
    # Missing/disabled rules stay explicit; the model's component weights never change.
    return Decimal(int(any(item["status"] == "HIT" for item in evidence))), evidence
