"""Synthetic scoring inspection/sabotage restricted to the disposable integration DB."""

import json
import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import database_engine
from app.ingestion.storage import PrivateStorage
from app.ml import artifacts
from app.models import (
    Alert,
    AuditLog,
    Membership,
    ModelVersion,
    Organization,
    RiskSettings,
    RuleDefinition,
    ScoringResult,
    Transaction,
    TransactionLabel,
    User,
)
from app.scoring.calculation import band, composite
from app.seed import ORGANIZATION_NAME

settings = get_settings()
assert settings.app_env == "local" and settings.postgres_db == "sentinelai_ingestion_test"
engine = database_engine(settings.database_url)
try:
    with Session(engine) as db, db.begin():
        assert db.scalar(text("SELECT current_database()")) == "sentinelai_ingestion_test"
        org = db.scalars(select(Organization).where(Organization.name == ORGANIZATION_NAME)).one()
        mode = sys.argv[1]
        if mode == "rules":
            assert not db.scalar(
                select(RuleDefinition.id).where(RuleDefinition.organization_id == org.id)
            )
            rules = [
                RuleDefinition(
                    organization_id=org.id,
                    code=code,
                    description="Fictional integration rule",
                    parameters_json=params,
                )
                for code, params in (
                    ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 1}),
                    ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 2}),
                    ("DEVICE_CHANGE", {}),
                )
            ]
            db.add_all(rules)
            db.flush()
            print(json.dumps({rule.code: str(rule.id) for rule in rules}))
        elif mode == "threshold":
            db.get(RiskSettings, org.id).alert_threshold = 0
        elif mode == "isolation":
            foreign = Organization(name="Fictional isolated scoring organization")
            db.add(foreign)
            db.flush()
            membership = db.scalars(
                select(Membership)
                .join(User)
                .where(
                    User.email == "analyst@sentinel-demo.invalid",
                    Membership.organization_id == org.id,
                )
            ).one()
            membership.organization_id = foreign.id
        elif mode == "tamper":
            model = db.scalars(
                select(ModelVersion).where(
                    ModelVersion.organization_id == org.id, ModelVersion.is_active.is_(True)
                )
            ).one()
            storage = PrivateStorage(settings)
            try:
                artifacts.put(storage, org.id, model.id, b"corrupt disposable model")
            finally:
                storage.close()
        else:
            assert mode == "verify"
            transactions = list(
                db.scalars(select(Transaction).where(Transaction.organization_id == org.id))
            )
            scores = list(
                db.scalars(
                    select(ScoringResult)
                    .join(Transaction)
                    .where(Transaction.organization_id == org.id)
                )
            )
            alerts = db.scalar(
                select(func.count()).select_from(Alert).where(Alert.organization_id == org.id)
            )
            labels = db.scalar(
                select(func.count())
                .select_from(TransactionLabel)
                .join(Transaction)
                .where(Transaction.organization_id == org.id)
            )
            audits = db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.organization_id == org.id, AuditLog.action == "TRANSACTION_SCORED")
            )
            assert len(transactions) == len(scores) == alerts == audits == int(sys.argv[2])
            assert labels == int(sys.argv[3])
            for score in scores:
                assert score.risk_score == composite(
                    score.supervised_probability,
                    score.anomaly_percentile,
                    score.rule_signal,
                    score.explanation_json["weights"],
                )
                assert score.risk_band == band(score.risk_score, score.settings_snapshot_json)
                assert score.explanation_status == "PARTIAL" and score.rule_signal == 0
            print(
                json.dumps(
                    {
                        "transactions": len(transactions),
                        "scores": len(scores),
                        "alerts": alerts,
                        "labels": labels,
                        "audits": audits,
                    }
                )
            )
finally:
    engine.dispose()
